from random import randint

DIGIT = ['0','1','2','3','4','5','6','7','8','9']
XDIGIT = DIGIT + ['b','c','d','f','g','h','j','k','m','n','p','q','r','s','t','v','w','x','z']
GENTYPES = ['r', 's', 'z']
DIGTYPES = ['d', 'e']
#SHORT = '.shrt.'
SHORT = ''

def mint(template='eeddeede', n=None, scheme=None, naa=None):
    if '.' in template:
        prefix, mask = template.rsplit('.', 1)
    else:
        mask = template
        prefix = ''

    try:
        __validateMask(mask)
    except:
        raise

    if n == None:
        if mask[0] in (GENTYPES):
            mask = mask[1:]
        # If we hit this point, this is a random (and therefore, short-term) identifier. 
        prefix = SHORT + prefix
        n = randint(0, __getTotal(mask) -1)

    noid = prefix + __n2xdig(n, mask)
    if naa:
        noid = naa.strip('/') + '/' + noid
    if template[-1] == 'k':
        noid += __checkdigit(noid)
    if scheme:
        noid = scheme + noid

    return noid

def validate(s):
    '''Checks if the final character is a valid checkdigit for the id. Will fail for ids with no checkdigit.

    This will also attempt to strip scheme strings (eg. 'doi:', 'ark:/') from the beginning of the string. This feature is limited, however, so if you haven't tested with your particular namespace, it's best to pass in ids with that data removed.

    Returns True on success, ValidationError on failure.
    '''
    if not __checkdigit(s[0:-1]) == s[-1]:
        raise ValidationError("Noid check character '" + s[-1] + "' doesn't match up for '" + s + "'.")
    return True


def __n2xdig(n, mask):
    req = n
    xdig = ''
    for c in mask[::-1]:
        if c == 'e':
            div = len(XDIGIT)
        elif c == 'd':
            div = len(DIGIT)
        else:
            continue
        value = n % div
        n = n // div
        xdig += (XDIGIT[value])
        
    if mask[0] == 'z':
        c = mask[1]
        while n > 0:
            if c == 'e':
                div = len(XDIGIT)
            elif c == 'd':
                div = len(DIGIT)
            else:
                raise InvalidTemplateError("Template mask is corrupt. Cannot process character: " + c)
            value = n % div
            n = n // div
            xdig += (XDIGIT[value])
        
    # if there is still something left over, we've exceeded our namespace. 
    # checks elsewhere should prevent this case from ever evaluating true.
    if n > 0:
        raise NamespaceError("Cannot mint a noid for (counter = " + str(req) + ") within this namespace.")
    
    return xdig[::-1]


def __validateMask(mask):
    masks = ['e', 'd']
    checkchar = ['k']

    if not (mask[0] in GENTYPES or mask[0] in masks):
        raise InvalidTemplateError("Template is invalid.")
    elif not (mask[-1] in checkchar or mask[-1] in masks):
        raise InvalidTemplateError("Template is invalid.")
    else:
        for maskchar in mask[1:-1]:
            if not (maskchar in masks):
                raise InvalidTemplateError("Template is invalid.")

    return True         


def __getTotal(mask):
    if mask[0] == 'z':
        total = NOLIMIT
    else:
        total = 1
        for c in mask:
            if c == 'e':
                total *= len(XDIGIT)
            elif c == 'd':
                total *= len(DIGIT)
    return total            
        

def __checkdigit(s):
    # TODO: Fix checkdigit to autostrip scheme names shorter or longer than 3 chars.
    try:
        if s[3] == ':':
            s = s[4:].lstrip('/')
    except IndexError:
        pass
    def ordinal(x):
        try: return XDIGIT.index(x)
        except: return 0
    return XDIGIT[sum([x * (i+1) for i, x in enumerate(map(ordinal,s))]) % len(XDIGIT)]