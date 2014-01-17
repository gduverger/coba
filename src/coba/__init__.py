#!/usr/bin/env python
__author__ = "Eric Pruitt <eric.pruitt@gmail.com>"
__license__ = "2-Clause BSD"

import collections
import cookielib
import datetime
import decimal
import errno
import re

import bs4
import mechanize
import zope.testbrowser.browser

# Not actually used here, but the module must be imported to initiate
# monkey-patching.
import urllib2_ssl

try:
    import cPickle as pickle
except ImportError:
    import pickle

__all__ = ["ChaseOnlineBankingError", "ChaseOnlineBankingAgent",
    "ChaseBankAccount", "ChaseCreditAccount", "ChaseDebitAccount", "wordize",
    "DebitAccountTransaction", "CreditAccountTransaction", "CALL_VERIFICATION",
    "EMAIL_VERIFICATION", "TEXT_MESSAGE_VERIFICATION", "PAY_STATEMENT_BALANCE",
    "PAY_CURRENT_BALANCE", "PAY_MINIMUM_BALANCE"]

CALL_VERIFICATION = 'L'
EMAIL_VERIFICATION = 'E'
TEXT_MESSAGE_VERIFICATION = 'X'
PAY_STATEMENT_BALANCE = 'T'
PAY_CURRENT_BALANCE = 'C'
PAY_MINIMUM_BALANCE = 'M'

DebitAccountTransaction = collections.namedtuple('DebitAccountTransaction',
    'name date amount balance')
CreditAccountTransaction = collections.namedtuple('CreditAccountTransaction',
    'name date type id amount memo')


class ChaseOnlineBankingError(Exception):
    """
    Error thrown by Chase Online Mobile banking.
    """


class ChaseOnlineBankingAgent:
    chasemobileloginurl = 'https://mobilebanking.chase.com/Public/Home/LogOn'
    accountslisturl = 'https://mobilebanking.chase.com/Secure/Accounts/'

    def __init__(self, username, password, otp_type=None, cookiefile=None,
      useragent='COBA/Python (+https://github.com/ericpruitt)'):
        self.username = username
        self.password = password
        self.cookiefile = cookiefile
        self.otp_type = otp_type or EMAIL_VERIFICATION

        self.mech_browser = mech_browser = mechanize.Browser()
        mech_browser.addheaders = [("User-agent", useragent)]
        mech_browser.set_handle_robots(False)

        # There's a refresh with a 760 second delay sent by Chase's server
        # presumably to automatically log out the user, so the refresh handler
        # must be disabled.
        mech_browser.set_handle_refresh(False)

        if cookiefile:
            self.cookiejar = cookiejar = cookielib.LWPCookieJar()

            mech_browser.set_cookiejar(cookiejar)
            self.load_cookies()

        self.browser = zope.testbrowser.browser.Browser(mech_browser=mech_browser)
        self.navigate(self.accountslisturl)

    def navigate(self, url):
        """
        Open a URL, but if the session has expired, attempt to log in first.
        """
        self.browser.open(url)
        soup = bs4.BeautifulSoup(self.browser.contents)
        if soup.find(id='auth_form'):
            self.login()

        self.save_cookies()
        return self.browser.contents

    def login(self, otp_type=None, otp=None, otp_prompt_call=None):
        """
        Log into Chase Mobile Banking. The `otp` argument is the temporary,
        one-time password that Chase requires when the account is accessed from
        an unrecognized system which I believe is determined by a combination
        of the User-Agent and IP address. If the `otp` argument is omitted and
        the banking system requires a temporary password, the temporary
        password will be sent out by way of a phone call, text message or email
        which is determined by the `otp_type` argument which can be set to
        `TEXT_MESSAGE_VERIFICATION`, `EMAIL_VERIFICATION`, or
        `CALL_VERIFICATION`, and the application will prompt for the O.T.P.
        """
        # Figure out what the anchor text will contain based on the OTP
        # password destination.
        otp_link_substring = {
            TEXT_MESSAGE_VERIFICATION: 'text me',
            EMAIL_VERIFICATION: '@',
            CALL_VERIFICATION: 'call_me',
        }[otp_type or self.otp_type or EMAIL_VERIFICATION]

        def fill_password():
            """Enter password into form."""
            password_field = self.browser.getControl(name='auth_passwd')
            password_field.value = self.password

        def fill_otp():
            """Enter O.T.P. into form."""
            otp_field = self.browser.getControl(name='auth_otp')
            otp_field.value = otp

        # Attempt to log in with the username and password
        self.browser.open(self.chasemobileloginurl)
        username_field = self.browser.getControl(name='auth_userId')
        username_field.value = self.username
        fill_password()

        login_form = self.browser.getForm(id='auth_form')
        login_form.submit()
        self.check_for_errors()

        html = self.browser.contents
        if 'EnterActivationCode' in html:
            if otp:
                # Submit OTP passed into method call
                self.browser.getLink('Already Have').click()
                fill_otp()
                fill_password()
                self.browser.getControl(name='Next').click()

            else:
                # Request OTP be sent to the user and await input.
                self.browser.getControl(name='Next').click()
                verification_link = self.browser.getLink(otp_link_substring)
                self.browser.open(verification_link.url)

                if not otp_prompt_call:
                    otp = raw_input('Verification Code: ')
                else:
                    otp = otp_prompt_call()

                if otp:
                    otp = otp.strip()
                    fill_otp()
                    fill_password()

                    self.browser.getControl(name='Next').click()

        self.save_cookies()
        self.check_for_errors()

    def save_cookies(self):
        """
        Serialize and save the session cookies.
        """
        if self.cookiefile:
            # [B] Set ignore_discard so ephemeral cookies that would normally
            # not be saved by the browser between sessions are preserved
            # anyway. Ensures different instances of the program can resume a
            # previous session.
            self.cookiejar.save(self.cookiefile, ignore_discard=True,
                ignore_expires=False)

    def load_cookies(self):
        """
        Load serialized cookies from the cookie jar file.
        """
        try:
            # See [B]
            self.cookiejar.load(self.cookiefile, ignore_discard=True,
                ignore_expires=False)
        except IOError as exc:
            if exc.errno != errno.ENOENT:
                raise

    def check_for_errors(self):
        """
        Raise an exception if any application warnings / errors are found in
        the page contents.
        """
        soup = bs4.BeautifulSoup(self.browser.contents)
        coaching_tag = soup.find(class_='coaching')
        if coaching_tag:
            if (coaching_tag.get('href') and
              coaching_tag['href'].endswith('/Announcement')):
                return

            coaching_text = ' '.join(coaching_tag.find_all(text=True)).strip()
            raise ChaseOnlineBankingError(coaching_text)

    @property
    def accounts(self):
        """
        Return ChaseBankAccount subclass instances representing the user's
        debit and credit accounts.
        """
        soup = bs4.BeautifulSoup(self.navigate(self.accountslisturl))
        tables = soup.find_all('table')
        if len(tables) != 1:
            raise ValueError('Expected 1 table, found %d.' % len(tables))

        table = tables[0]
        attributes = dict()
        constructor = dict()
        for row in table.find_all('tr'):
            columns = row.find_all('td')

            if len(columns) == 1:
                rowtext = ' '.join(row.find_all(text=True)).strip()
                if not constructor:
                    # Attributes used for the ChaseCreditAccount constructor.
                    try:
                        constructor['id_'] = columns[0]['id']
                    except KeyError:
                        # If there's no "id" attribute, we've hit the end of
                        # the account rows.
                        break

                    constructor['agent'] = self
                    constructor['url'] = row.a['href']
                    constructor['name'] = ' '.join(row.a.contents).strip()

                elif 'Transfer Money' in rowtext:
                    # URL used to initiate a transfer from debit account
                    attributes['transfer_from_url'] = row.a['href']

                elif 'Pay Credit Card' in rowtext:
                    # URL used to initiate a transfer from debit account
                    attributes['payment_url'] = row.a['href']

                elif row.a and 'CreditCardRewardDetails' in row.a['href']:
                    # Credit card rewards program information
                    attributes['rewards_program'] = rowtext
                    attributes['rewards_program_url'] = row.a['href']

                elif row.hr:
                    # Each account row is terminated with a horizontal rule.
                    # Select the constructor needed for the account type and
                    # yield the instantiated object.
                    if 'available_credit' in attributes:
                        class_ = ChaseCreditAccount
                    else:
                        class_ = ChaseDebitAccount

                    yield class_(attributes=attributes, **constructor)

                    constructor = dict()
                    attributes = dict()

            else:
                # [A] Wordize the left column and use it as the key for the
                # value in the right column. Any monetary amounts will be
                # converted to Decimal objects and dates to datetime objects.
                left_column, right_column = columns
                key = wordize(' '.join(left_column.contents))
                value = ' '.join(right_column.contents).strip()
                if value.startswith(('$', '-$')):
                    value = decimal.Decimal(re.sub('[^0-9.-]+', '', value))
                elif '/' in value:
                    try:
                        m, d, y = map(int, value.split('/'))
                        value = datetime.datetime(y, m, d)
                    except ValueError:
                        # Probably not a date
                        pass

                attributes[key] = value


class ChaseBankAccount(object):
    """
    Generic bank account class that implements functionality shared by all
    account types.
    """
    def __init__(self, agent, name, url, id_, attributes=None):
        self.attributes = attributes or dict()
        self.agent = agent
        self.name = name
        self.url = url
        self.id_ = id_

    def __repr__(self):
        return '%s(agent=%r, name=%r, url=%r, id_=%r, attributes=%r)' % (
            self.agent, self.name, self.url, self.id_, self.attributes)

    def __str__(self):
        return self.name

    def __setattr__(self, name, value):
        if name == 'attributes' or not hasattr(self, 'attributes'):
            object.__setattr__(self, name, value)
        elif name in self.attributes:
            raise TypeError('Attribute "%s" is read-only.' % name)
        else:
            object.__setattr__(self, name, value)

    def __getattr__(self, name):
        try:
            return self.attributes[name]
        except KeyError:
            raise AttributeError('Attribute "%s" not found.' % name)

    def transactions(self, since=None, through=None, maxpages=100):
        """
        Get accounts transactions starting from the date specified by `since`
        through the date specified by `through`. If `since` is not specified,
        no lower bound is set, and when `through` not specified, no upper bound
        on the transaction dates is set. The number of pages of transactions
        that will be examined regardless of the date range can is controlled by
        the value of `maxpages`.
        """
        # Column names -> Transaction constructor values
        row_key_map = {
            'balance': 'balance',
            'transaction_date': 'date',
            'date': 'date',
            'type': 'type',
            'memo_description': 'memo',
            'transaction_number': 'id',
            'debit_credit_amount': 'amount',
            'debit_credit': 'amount',
        }

        if not through:
            through = datetime.datetime(3000, 1, 1)
        if not since:
            since = datetime.datetime(1, 1, 1)

        now = datetime.datetime.now()

        page = self.url
        nones = [None for _ in range(len(self.transaction_class._fields))]
        constructor_defaults = zip(self.transaction_class._fields, nones)
        constructor = dict(constructor_defaults)
        while maxpages:
            maxpages -= 1
            soup = bs4.BeautifulSoup(self.agent.navigate(page))
            tables = soup.find_all('table')
            # For some reason, the transactions page has an empty table.
            if len(tables) != 2:
                raise ValueError('Expected 2 tables, found %d.' % len(tables))

            table = tables[1]
            for row in table.find_all('tr'):
                columns = row.find_all('td')

                if len(columns) == 1:
                    rowtext = ' '.join(row.find_all(text=True)).strip()
                    if constructor['name'] is None:
                        # Condense concurrent whitespace into a single space.
                        constructor['name'] = re.sub('\s+', ' ', rowtext)

                    elif row.hr:
                        transaction = self.transaction_class(**constructor)
                        if (transaction.date or now) < since:
                            return

                        if through >= (transaction.date or now) >= since:
                            yield transaction
                        constructor = dict(constructor_defaults)

                else:
                    # Refer to [A] for commentary.
                    left_column, right_column = columns
                    key = wordize(' '.join(left_column.contents))
                    try:
                        constructor_key = row_key_map[key]
                    except KeyError:
                        # XXX: Should probably log a warning
                        continue

                    value = ' '.join(right_column.contents).strip()
                    if value.startswith(('$', '-$')):
                        value = decimal.Decimal(re.sub('[^0-9.-]+', '', value))
                    elif value == '--' or (not value and key != 'memo'):
                        value = None
                    elif constructor_key == 'date':
                        if value == 'Pending':
                            value = None
                        else:
                            m, d, y = map(int, value.split('/'))
                            value = datetime.datetime(y, m, d)

                    constructor[constructor_key] = value

            try:
                page = soup.find(text='Next').parent['href']
            except AttributeError:
                # No more pages
                return


class ChaseCreditAccount(ChaseBankAccount):
    """
    Credit banking account, i.e. credit cards.
    """
    transaction_class = CreditAccountTransaction

    def pay_from(self, other, amount, date=None):
        """
        Pay off account balance using a debit account. The amount can be a
        number or one of the constants `PAY_STATEMENT_BALANCE`,
        `PAY_CURRENT_BALANCE`, or `PAY_MINIMUM_BALANCE` which will
        automatically pay the statement balance, current balance and minimum
        payment respectively. An exception will be thrown if there are any
        issues processing the payment, and the balance paid will be returned if
        the payment is successfully scheduled. Not all debit accounts can be
        used to pay off credit account balances; things like savings accounts
        are generally not permitted as a source of payment.
        """
        if not isinstance(other, ChaseDebitAccount):
            raise TypeError('`other` must be a ChaseDebitAccount instance.')

        payopts = (PAY_STATEMENT_BALANCE, PAY_CURRENT_BALANCE,
          PAY_MINIMUM_BALANCE)

        if amount not in payopts:
            # Verify that the amount is a number
            amount = str(amount)
            try:
                float(amount)
            except ValueError:
                raise ValueError('%r does not appear to be a number.' % amount)

        # Find the URL used to initiate a transfer to the other account
        soup = bs4.BeautifulSoup(self.agent.navigate(self.payment_url))
        regex = re.compile(re.escape(other.name))
        match = soup.find('a', text=regex)

        if match:
            url = match['href']
        else:
            raise ValueError('%s cannot be used for payment.' % other)

        # Scan page for payment options
        payment_type_map = dict()
        soup = bs4.BeautifulSoup(self.agent.navigate(url))
        options = soup.find_all(id='PaymentOptionId')
        if not options:
            # XXX: Should probably pick a better exception
            raise Exception('Unable to find payment options.')

        for option in options:
            control_label = ' '.join(option.parent.parent.find_all(text=True))
            if 'Statement balance' in control_label:
                payment_type_map[PAY_STATEMENT_BALANCE] = option['value']
            elif 'Current Balance' in control_label:
                payment_type_map[PAY_CURRENT_BALANCE] = option['value']
            elif 'Minimum payment' in control_label:
                payment_type_map[PAY_MINIMUM_BALANCE] = option['value']
            elif 'Other amount' in control_label:
                payment_type_map[None] = option['value']

        # Select button for payment option and fill in amount if needed.
        radiobuttons = self.agent.browser.getControl(name='PaymentOptionId')
        if amount not in payopts:
            self.agent.browser.getControl(name='Amount').value = amount
            button = radiobuttons.getControl(value=payment_type_map[None])
        else:
            if amount not in payment_type_map:
                raise ValueError('Selected payment type cannot be used.')
            button = radiobuttons.getControl(value=payment_type_map[amount])

        button.selected = True
        self.agent.browser.getControl(name='Submit').click()
        self.agent.check_for_errors()

        if amount in payopts:
            soup = bs4.BeautifulSoup(self.agent.browser.contents)
            tables = soup.find_all('table')
            if len(tables) != 1:
                raise ValueError('Expected 1 table, found %d.' % len(tables))

            table = tables[0]
            rows = table.find_all('tr')
            for row in rows:
                row_text = ' '.join(row.find_all(text=True)).strip()
                if 'Total payment amount:' in row_text:
                    usd = row_text.split()[-1]
                    payment = decimal.Decimal(usd[1:])
                    break
            else:
                raise Exception('Could not scrape total payment amount.')


        # Submit amount selection form
        self.agent.browser.getControl(name='Submit').click()
        self.agent.check_for_errors()

        # Submit confirmation page agreement
        self.agent.browser.getControl(name='Submit').click()
        self.agent.check_for_errors()

        if 'Step 4 of 4' not in self.agent.browser.contents:
            raise Exception('Unknown problem while submitting transfer.')

        return payment


class ChaseDebitAccount(ChaseBankAccount):
    """
    Debit banking account, e.g. savings and checking.
    """
    transaction_class = DebitAccountTransaction

    def transfer_to(self, other, amount, memo='', date=None):
        """
        Transfer funds from this debit account to another debit account. The
        `amount` can be anything that 
        """
        if not isinstance(other, ChaseDebitAccount):
            raise TypeError('Argument must be a ChaseDebitAccount instance.')

        try:
            amount = str(decimal.Decimal(amount))
        except decimal.InvalidOperation:
            raise ValueError('%r does not appear to be a number.' % amount)

        # Find the URL used to initiate a transfer to the other account
        soup = bs4.BeautifulSoup(self.agent.navigate(self.transfer_from_url))
        for link in soup.find_all('a'):
            url = link['href']
            if re.search('\\btoId=%s\\b' % other.id_, url):
                break
        else:
            raise ValueError('%s not in available transfers list.' % other)

        # Fill out the transfer form and submit it.
        self.agent.navigate(url)
        try:
            transfer_form_action = "/Secure/Transfer/Transfer/EnterDetails"
            form = self.agent.browser.getForm(action=transfer_form_action)
        except LookupError:
            raise LookupError('Unable to locate transfer form.')

        if date:
            form.getControl(name='DeliverByDate').value = date
        form.getControl(name='Memo').value = memo
        form.getControl(name='Amount').value = str(amount)
        self.agent.browser.getControl(name='Next').click()

        self.agent.check_for_errors()
        if 'Verify' not in self.agent.browser.url:
            raise ValueError('Unexpected URL %r.', self.agent.browser.url)

        # Click through the verification / confirmation page.
        self.agent.browser.getControl('Submit').click()
        self.agent.check_for_errors()

        if 'Step 5 of 5' not in self.agent.browser.contents:
            raise Exception('Unknown problem while submitting transfer.')

    def transfer_from(self, other, amount, memo='', date=None):
        other.transfer_to(self, amount, memo=memo, date=date)


def wordize(text):
    """
    Replace characters not matching the regex "[a-z0-9_+]+" with
    underscores and remove any trailing and leading underscores.
    """
    return re.sub('\\b_|_\\b', '', re.sub('[^a-z0-9_-]+', '_', text.lower()))
