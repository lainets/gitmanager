DEBUG = True
#SECRET_KEY = 'not a very secret key'
ADMINS = (
)
#ALLOWED_HOSTS = ["*"]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'gitmanager',
    },
}

STATIC_ROOT = '/local/gitmanager/static/'
MEDIA_ROOT = '/local/gitmanager/media/'
SSH_KEY_PATH = '/etc/gitmanager/ssh/id_ecdsa'

# The scheme and hostname of where the static files can be accessed. Passed to build containers.
STATIC_CONTENT_HOST = 'http://localhost:8070'
# scheme and host for automatic updates.
FRONTEND_URL = 'http://plus:8000'
# default grader URL used for configuring
DEFAULT_GRADER_URL = 'http://grader:8080/configure'

# this MUST be on the same device as COURSES_PATH
STORE_PATH = '/srv/courses/course_store'
COURSES_PATH = '/srv/courses/publish'
BUILD_PATH = '/tmp/aplus/gitmanager/build'
LOCAL_COURSE_SOURCE_PATH = '/srv/courses/source'
# See the BUILD_MODULE script for details
BUILD_MODULE_SETTINGS = {
    'HOST_BUILD_PATH': BUILD_PATH,
    'CONTAINER_BUILD_PATH': BUILD_PATH,
    'HOST_PUBLISH_PATH': COURSES_PATH,
    'CONTAINER_PUBLISH_PATH': COURSES_PATH,
}

# Local messaging library settings
APLUS_AUTH_LOCAL = {
    "UID": "gitmanager",
    "PRIVATE_KEY": """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAsaVdUeIDB1TluqYgkxRa0JMxIoa1f6V0UpfR6eoa/RKyZS3A
2mp9Mjt9OXRB4sG9L+OQRm4kx03M2QyFPEszmcehmZ1kWXyXJHyhqnaUACm2bUKS
jexsfoHjZV4/KaFe7vdyPwXhpVQ876/DKApkOF6ugfeETx5tSfgWMerOjV6lqrgG
Ei9OvuymvJlY+Jgxi6uhZTbZntcQ0Dbpp7j5XHAshtEP2NOpefG/5v03zSILs9oU
aoAOSb2VMke9+/pg20vYYzYEcNbqUVMal88Lkb3lV9aulPi7rH+FGRZuI0/wFzWc
uLSupF1+YcwGprsm3seead90dRh6gYHXk8v12wIDAQABAoIBAFpXn7LRvvqOiVo3
vB8wXdLu2DEX0tu8mACc5wsPnHQRexoLf6VUPKE8Mb3zSsJ4Bq+BClFXGGsnPMMx
I9z63Z4aMSu/KFZ+DxtmKo1XSoMes4CzN3bnwnE/uxZFLNgOEgpzWu2EHzIGOgsn
FpeZWUh1lkfQScA22BujCB6QrESmAT3NJ3sQjsSThPHz2CJOGCAnz+Lm+WiIoWje
KlxNlKhHTUAjR9tEjQ0b0NvJDm33wvNabpjmJE5h0sFLsuofCfJVRrM5N2D0/idr
j91kiis5K7R6qynBU/UOygllZOj5ikGOQWRHDUevgEKPOIoR/mHNTvm/VGzJj0h1
g0XilNkCgYEA42tD43PPkW0J2fHsyah83WxXym8yoEiPTQnvdR2darKbW1ix8Ho4
qwfRrpHzZmysuMEOibyZ6SX+apvBYIC5QSVmd+fMSXNtaDRAjM1IvEj0+OD61P3e
epO3FtoxxVj1PZ5xBcFkkEkIKHDvt64ZIOCqlbtmjb9MaNav8+/nIA8CgYEAx/jB
NEaMlR3SaZKWyowxhfxJigXLWfo1OSbXGIhrFDbJH2CFLB2k5GzZdN+Q2SJo45yI
1x44YkquRGE+9/p7mUpKiwX2qCG3pW14v1ODHC84SoFk7YTpAYSqHO7mZJSRh7AX
GXJf4C5c3wXu/Oe7CXVVIzv8EXwXBQgpM4ERwXUCgYA6+V8Chc7G9JLAbOctqD6x
IN5nRYzIWeinXrM1GLfwql51QrvqE5fMaluqvHh1ECt+QbomZ701479lH/z2rIrd
5Pf8kiS8y20Mv7gZi0aYZQb530XMpATknpe1GmIbviTilMrUZkFQ1U+DRT400LX9
e6Vg7Nb8XSZQbZP1WzoBawKBgQC/C/TpkI022Wrw2c+eaxnVPBa1+pswt06p72WI
VqyWf1De3UPdxeSHJ0cJ1Z15FNrIugAyJPkRTu/2/EFAgNoctVFKSMRCFRRyw4ec
opicELDi3YQjN9u0S56KTeNnLFltHNq0wQTAFQs9N1n/3RRgEOzp4KENw1PqxsU2
I5VnEQKBgA9Kb/mwxelD2TrlvhkXG4kMFqi/k6BRc0dSvW/8REtg4NC/PILAizTA
lEYni9o8Sky60K9GNwIDDHcwDU+2t0rqoVXiP+8mmBsx/FpA9TUA5IeC5tbc0+vp
vtWaQFhmeWtGGdI/ysw9h6fyS3KaicY6zVB1BTyEMWnD0dk7Gera
-----END RSA PRIVATE KEY-----""",
    "PUBLIC_KEY": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsaVdUeIDB1TluqYgkxRa
0JMxIoa1f6V0UpfR6eoa/RKyZS3A2mp9Mjt9OXRB4sG9L+OQRm4kx03M2QyFPEsz
mcehmZ1kWXyXJHyhqnaUACm2bUKSjexsfoHjZV4/KaFe7vdyPwXhpVQ876/DKApk
OF6ugfeETx5tSfgWMerOjV6lqrgGEi9OvuymvJlY+Jgxi6uhZTbZntcQ0Dbpp7j5
XHAshtEP2NOpefG/5v03zSILs9oUaoAOSb2VMke9+/pg20vYYzYEcNbqUVMal88L
kb3lV9aulPi7rH+FGRZuI0/wFzWcuLSupF1+YcwGprsm3seead90dRh6gYHXk8v1
2wIDAQAB
-----END PUBLIC KEY-----""",
    "REMOTE_AUTHENTICATOR_KEY": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnME9k+VaxbUD2fGDgpKH
Ri6cE4T6HZzqWDpvtOShhoHSYQ6VlX0YnDQYwdDoTTK+XIBG2uS8W+3CsvpxjpHF
8Ny5xzxNGZTeqSn8A08BvoQ5cX7bnXOYUb4x2Pp/00WwaQseumUNP+ep/jCV+aqv
iWzOmX9p8zZGdFghvplbt9A173df4t6kICK11hUm14mpUtL/bCQ2xsUEmPGX+zw8
V1kynwJp2AaBuFVpkKDjHyHQJ+yotou01Vksp1kYoX21odjoZCivArEjuwzDEoHt
6WHPLnwvkBYouNA9jgR63mS1rW1PiloDlNNMFW1nR+AHjTfVSKKatnswO3JVLxYe
qwIDAQAB
-----END PUBLIC KEY-----""",
    "REMOTE_AUTHENTICATOR_URL": "http://plus:8000/api/v2/get-token/",
    "REMOTE_AUTHENTICATOR_UID": "aplus",
    "DISABLE_LOGIN_CHECKS": False,
    "DISABLE_JWT_SIGNING": False,
    "UID_TO_KEY": {
        "radar": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvddPdRsfeYjTK/aVnX/J
52exmXiu7ZXLx2W83brLmxaOGR1Zb0qFt+0rtvBAx+s9KjlRj8rmMBLpTUTWWeai
MpVHkhMH+MHAcL8jCfM8G5nLqcg2j50VBfXEiKT0QtonkOH+HVLYrtR0ZRQt4i9/
8XLi1z+oITlH30yqs19PvZVksIJjReLqRDI1bxdzs6296i2Js5PyvGNKY1cn52dq
MgMysg9P3HeuwAQW2jXQwxPn4HhNoKlQL2SpNvInWwmpS1PrXgIhEvEq+T79GcxI
eGJ1Rjhi6HY9jhFMYBh23EirAa+HRBAbcyQ01Cc8hUa2YoNoolD/3oadsfQshps8
8wIDAQAB
-----END PUBLIC KEY-----""",
     },
     "TRUSTED_UIDS": ["radar", "aplus"],
}
