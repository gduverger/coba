COBA, Chase Online Banking Agent
================================

COBA is a Python library that provides an interface to Chase Online Banking by
scraping the mobile version of the Chase Online website.

Neither the author nor this project itself, the Chase Online Banking Agent, are
in any way affiliated with or endorsed by the JPMorgan Chase company. "JPMorgan
Chase," "JPMorgan," "Chase," the Octagon Symbol, and other words or symbols
used within this project to identify JPMorgan Chase services are trademarks and
service marks of JPMorgan Chase & Co.

When using the Chase Online Banking Agent, you are interacting with the
[chase.com](https://www.chase.com/) website and subject to its documented
[terms and conditions](https://www.chase.com/resources/terms-conditions).

Although a best effort is made at ensuring the accuracy and reliability of the
information displayed by COBA and its functionality, the author offers no
warranty or guarantees COBA will work as expected and maintains no liability of
losses, financial or otherwise, that may occur through the use or misuse of
COBA.

Installation
------------

### Dependencies ###

COBA only supports Python 2.7 and depends on Beautiful Soup 4,
zope.testbrowser, and Mechanize. COBA monkey-patches httplib at run-time so it,
and in turn Mechanize and zope.testbrowser, properly validate SSL certificates.
As such, only Mechanize version 0.2 and zope.testbrowser 4.0 are supported
since future releases may make HTTP requests in a manner that bypasses the
monkey-patched SSL validation.

### Setup ###

A setup.py file is provided that will install the coba module and the cobcli, a
command line interface for interacting with Chase Online. Execute `python
setup.py install` using sudo or as privileged user to install the package
globally or run `python setup.py install --user` to install the package as the
current user. Once installed, you should be able to import the "coba" module in
Python and, provided your `PATH` environment variable is configured correctly,
run `cobcli` at the command line to launch the command line interface. The
default location for scripts packaged with Python modules is generally
`~/.local/bin`, but this can be changed using the
[--install-scripts](http://docs.python.org/2/install/#custom-installation)
option.

Chase Online Banking CLI (cobcli)
---------------------------------

Cobcli is a command line interface to Chase Online Banking. Its basic usage is
`cobcli [-f CONFIGURATION_FILE] [-c COMMAND]`, and it can be run with or
without specifying a configuration file with the "-f" option. When no
configuration file is specified, cobcli will attempt to load the configuration
from `~/.cobcli` if the file exists. The configuration file is a JSON object
that must contain the keys "username" and "password" with the Chase Online
Banking account credentials, and may optionally contain the keys "cookiefile",
the file that will be used to store session cookies, and "verification" which
can be "sms", "call", or "email" which will dictate the verification method
that should be used to send the identity verification code if Chase Online
Banking does not recognize the system you're logging in from. If the
verification method is unspecified, it will default to "email". When the
"cookiefile" is unspecified, cobcli will still work but subsequent instances of
the program will have to log in again instead of resuming the previous section
increasing the amount of time cobcli will need to execute commands. Here's an
example configuration file:

    {
        "username": "eric",
        "password": "hunter2",
        "cookiefile": "/dev/shm/coba-cookies.dat",
        "verification": "sms"
    }

If a configuration file is not used, a prompt for the username and password
will appear when cobcli is launched. Once the login credentials have been
provided, cobcli will handle any subsequent re-logins that are necessary due to
session timeouts automatically.

Commands can be specified as command line arguments using the "-c" flag, The
text is parsed in a roughly POSIX-shell compliant manner. Multiple commands can
be specified by separating them with non-escaped semicolons. For example, to
shows the balance of ones accounts and all transactions for the last week, the
following command could be used:

    cobcli -c 'accounts; transactions "since:one week ago"'

The following commands are recognized by cobcli:

### transfer ###

Transfer money from one debit account to another. Takes the amount and search
strings for the source and destination accounts as arguments in the following
form. In the following example, $2000 is transferred from the account that
contains "checking" in its name to the account the contains "saving" in its
name:

    transfer 2000 from checking to saving

Multiple qualifiers can be added in the event that the search terms match more
than one account. In this example below, $500 is transferred from a Chase Total
Checking account to a Chase Premier Plus Checking account:

    transfer 500 from premier checking to total checking

**Output Sample:**

    > transfer 5.50 from checking to saving
    Transferring 5.50 from TOTAL CHECKING (...1234) to CHASE SAVINGS (...4567).
    Proceed? (y/N) y
    Transfer of $5.50 submitted.

### details ###

List raw properties of an account or accounts. This command accepts optional
search terms as arguments, and accounts that contain any of the specified
strings will be included in the output. When no search terms are provided, the
properties of all accounts are displayed.

**Output Sample:**

    > details
    TOTAL CHECKING (...1243)
    ------------------------
    Present balance                                                   $1,000.00
    Available balance                                                 $1,000.00

    CHASE SAVINGS (...4567)
    -----------------------
    Withdrawals this period                                                   2
    Present balance                                                   $2,000.00
    Available balance                                                 $2,000.00

    CREDIT CARD (...8901)
    ---------------------
    Next payment due                                                 05/20/2014
    Total credit limit                                                  $300.00
    Current balance                                                     $400.00
    Last statement balance                                              $500.00
    Minimum payment due                                                  $60.00
    Available credit                                                     $70.00

### accounts ###

List accounts with names and balances. This command accepts optional search
terms as arguments, and accounts that contain any of the specified strings will
be included in the output. When no search terms are provided, a balance is
displayed below the unfiltered list of accounts. If one of the arguments is
"deduct-pending", the most recent transactions of credit accounts will be
inspected and any pending transactions will be used to adjust the balance which
normally ignores pending transactions. This comes at a cost of speed.

**Output Sample:**

    > accounts
    TOTAL CHECKING (...1234)                                            1000.00
    CHASE SAVINGS (...4567)                                             2000.00
    CREDIT CARD (...8901)        Marriott Rewards® Credit Card           270.00
    ---
    Balance:                                                            2730.00

### transactions ###

List transactions from accounts. This command accepts optional search terms as
arguments, and accounts that contain any of the specified strings will have
their transactions included in the output. When no search terms are provided,
transactions from all accounts are shown. A date range can also be specified by
passing in arguments starting with "from:" or "since:" for the starting date
and "through:" or "to:" for the ending date. Because GNU date(1) is used for
parsing the date, many common, human-readable forms of dates are accepted. Here
are some examples:

Show transactions from April 25th, 2013 through May 1st, 2013 in accounts that
have "credit" in the name.

    transactions from:2013-04-25 through:2013-05-01 credit

Show transactions from one week ago through the present date; note that
omitting an end date implies "through the current date" whereas omitting the
start date implies "since the beginning of time":

    transactions "from:one week ago"

In addition to the date range selectors, minimum and maximum transaction
amounts can be specified with the "min:" and "max:" prefixes respectively, and
transaction names can be searched using the "contains:" prefix.

To show transactions containing the text "target," the following command would
be executed:

    transactions contains:target

And to show transactions between $25 and $100:

    transactions min:25 max:100

**Output Sample:**

    > transactions since:2014-01-01 to:2014-01-07 credit
    Showing transactions since January 01, 2014 through January 07, 2014
    WAL-MART #1234 (Other)                                 2014-01-01     50.00
    TEXACO (Other)                                         2014-01-03     40.35
    BEST BUY (Other)                                       2014-01-04    108.24
    NETFLIX.COM (Other)                                    2014-01-04      8.65
    BIG LOTS STORES (Other)                                2014-01-05     10.00
    COTTON PATCH CAFE - LU (Other)                         2014-01-05     32.44
    Payment Thank You - Web (Other)                        2014-01-05   -123.45
    TCBY (Other)                                           2014-01-07      6.48

### pay ###

Pay off the balance of a credit account. Takes the amount and search strings
for the source and destination accounts as arguments in the following form:
(amount) on (destination) with (source). The amount can also be specified as
"statement", "minimum", or "current" to pay off the previous statement balance,
make the minimum payment or pay off the current balance respectively. In the
following example, $500 is paid against the balance of the credit card
containing the text "amazon" from the debit account containing the text
"checking:"

    pay 500 on amazon with checking

As with account transfers, multiple strings can be used as qualifiers to narrow
down the selected account.

**Output Sample:**

    > pay 70 on marriott with checking
    Paying 70.00 on CREDIT CARD (...8901) with TOTAL CHECKING (...1234).
    Proceed? (y/N) y
    Payment of $70.00 submitted.
