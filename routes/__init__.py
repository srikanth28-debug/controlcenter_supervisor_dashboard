
from utils.http import respond as __respond, cors_headers as __cors_headers
from utils.logger import get_logger as __get_logger
from utils.aws_clients import ddb as __DDB, connect as __CONNECT, table as __table

# Standardize helpers across routes (backwards-compatible)
try:
    _response
except NameError:
    _response = __respond
try:
    _cors_headers
except NameError:
    _cors_headers = __cors_headers
try:
    DDB
except NameError:
    DDB = __DDB
try:
    CONNECT
except NameError:
    CONNECT = __CONNECT

