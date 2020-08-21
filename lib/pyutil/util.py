
import hashlib
import os
import random
import re
import string
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import traceback


class Util:

    def __init__(self):
        super(Util, self).__init__()

    @staticmethod
    def string_contains_any(str, set):
        for c in set:
            if c in str:
                return 1
        return 0

    @staticmethod
    def string_count_contains(str, set):
        count = 0
        for c in set:
            if c in str:
                count += 1
        return count


    @staticmethod
    def random_password(length=8, minimum_numbers=1, minimum_alphas_lower=1,
                        minimum_alphas_upper=1, minimum_nonalphas=1,
                        specials=True, exclusions=None):
        special_chars = '!@#$%^*'
        if specials:
            chars = string.ascii_letters + string.digits + special_chars
        else:
            chars = string.ascii_letters + string.digits
        random.seed = (os.urandom(1024))

        while True:
            password = StringIO()

            for _ in range(length):
                while True:
                    current = password.getvalue()
                    char = random.choice(chars)
                    new = "{}{}".format(current, char)

                    # test exclusions (forwards and backwards)
                    if exclusions:
                        for x in exclusions:
                            if re.search(x, new) or re.search(x[::-1], new):
                                continue
                    password.write(str(char))
                    break

            # Sanity checks
            password = password.getvalue()

            # Check password contains minimum number count
            if not Util.string_count_contains(password, string.digits) >= minimum_numbers:
                continue

            # Check password contains minimum lower alphas count
            if not Util.string_count_contains(password, string.ascii_lowercase) >= minimum_alphas_lower:
                continue

            # Check password contains minimum upper alphas count
            if not Util.string_count_contains(password, string.ascii_uppercase) >= minimum_alphas_upper:
                continue

            # Check password contains minimum special count
            if specials and not Util.string_count_contains(password, special_chars) >= minimum_nonalphas:
                continue

            break

        return password

    @staticmethod
    def random_passcode(length=6, repeating_limit=2, sequential_limit=3, exclusions=None):
        password = StringIO()
        chars = "0123456789"
        random.seed = (os.urandom(1024))

        for _ in range(length):
            while True:
                current = password.getvalue()
                char = random.choice(chars)

                new = "{}{}".format(current, char)

                # test exclusions (forwards and backwards)
                if exclusions:
                    excluded = False
                    for x in exclusions:
                        if re.search(x, new) or re.search(x[::-1], new):
                            excluded = True
                            break
                    if excluded:
                        continue


                # test repeating digits
                if len(current) >= repeating_limit - 1:
                    check_digits = new[-(repeating_limit):]
                    if check_digits == len(check_digits) * check_digits[0]:
                        continue

                # test sequential digits
                if len(current) >= sequential_limit - 1:
                    check_digits = new[-(sequential_limit):]
                    # check if last digits are sequential (forward), if not...care
                    l = None
                    s_count = 0
                    for digit in check_digits:
                        if l:
                            if int(digit) == l+1:
                                s_count += 1
                        l = int(digit)
                    if s_count == sequential_limit - 1:
                        continue

                    # check if last digits are sequential (reverse), if not...care
                    l = None
                    s_count = 0
                    for digit in check_digits:
                        if l:
                            if int(digit) == l-1:
                                s_count += 1
                        l = int(digit)
                    if s_count == sequential_limit - 1:
                        continue

                password.write(char)
                break

        return password.getvalue()

    @staticmethod
    def str_empty_to_none(value):
        return None if value == '' else value

    @staticmethod
    def base36encode(number, alphabet='0123456789abcdefghijlkmnopqrstuvwxyz'):
        """Converts an integer to a base36 string."""
        if not isinstance(number, (int, long)):
            raise TypeError('number must be an integer')

        base36 = ''
        sign = ''

        if number < 0:
            sign = '-'
            number = -number

        if 0 <= number < len(alphabet):
            return sign + alphabet[number]

        while number != 0:
            number, i = divmod(number, len(alphabet))
            base36 = alphabet[i] + base36

        return sign + base36

    @staticmethod
    def base36decode(number):
        return int(number, 36)

    @staticmethod
    def dn_range_to_list(dn_range):
        dn_range = dn_range.split(' - ')
        if len(dn_range) == 2:
            # iterate over the numbers
            start_cc = dn_range[0].split('-')[0]
            start_dn = dn_range[0].split('-')[1]
            end_cc = dn_range[1].split('-')[0]
            end_dn = dn_range[1].split('-')[1]
            r = range(int(start_dn), int(end_dn)+1)
            if start_cc != end_cc:
               raise Exception('Could not parse range: numbers not in same cc')
            dn_range = []
            for n in r:
                dn_range.append("{}-{}".format(start_cc, n))
            return dn_range
        else:
            return dn_range

    @staticmethod
    def md5(fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
