#    @Author: Justin C Presley
#    @Author-Email: justincpresley@gmail.com
#    @Project: NDN State Vector Sync Protocol
#    @Source-Code: https://github.com/justincpresley/ndn-python-svs
#    @Pip-Library: https://pypi.org/project/ndn-svs/

# Basic Libraries
from typing import Callable, Optional
import logging
# NDN Imports
from ndn.app import NDNApp
from ndn.encoding import Name, Component, make_data, MetaInfo
from ndn.encoding import parse_data
from ndn.types import InterestNack, InterestTimeout, InterestCanceled, ValidationFailure
from ndn_python_repo import Storage
# Custom Imports
from .svs_base import SVSyncBase
from .security import SecurityOptions

# Class Type: an derived API class
# Class Purpose:
#   to allow the user to interact with SVS, fetch and publish.
#   to allow caching other node's data in case one node goes down.
class SVSyncShared(SVSyncBase):
    def __init__(self, app:NDNApp, groupPrefix:Name, nid:Name, updateCallback:Callable, cacheOthers:bool, storage:Optional[Storage]=None, securityOptions:Optional[SecurityOptions]=None) -> None:
        self.cacheOthers = cacheOthers
        self.groupPrefix = groupPrefix
        preDataPrefix = groupPrefix + [Component.from_str("d")] if self.cacheOthers else groupPrefix + [Component.from_str("d")] + nid
        preSyncPrefix = groupPrefix + [Component.from_str("s")]
        super().__init__(app, preSyncPrefix, preDataPrefix, nid, updateCallback, storage, securityOptions)
    async def fetchData(self, nid:Name, seqNum:int, retries:int=0) -> Optional[bytes]:
        name = self.getDataName(nid, seqNum)
        while retries+1 > 0:
            try:
                logging.info(f'SVSync: fetching data {Name.to_str(name)}')
                _, _, _, pkt = await self.app.express_interest(name, need_raw_packet=True, must_be_fresh=True, can_be_prefix=False, lifetime=6000)
                ex_int_name, meta_info, content, sig_ptrs = parse_data(pkt)
                isValidated = self.secOptions.validate(ex_int_name, sig_ptrs)
                if not isValidated:
                    return None
                logging.info(f'SVSync: received data {bytes(content)}')
                if content and self.cacheOthers:
                    logging.info(f'SVSync: publishing others data {Name.to_str(name)}')
                    self.storage.put_data_packet(name, pkt)
                return bytes(content) if content else None
            except InterestNack as e:
                logging.warning(f'SVSync: nacked with reason={e.reason}')
            except InterestTimeout:
                logging.warning(f'SVSync: timeout')
            except InterestCanceled:
                logging.warning(f'SVSync: canceled')
            except ValidationFailure:
                logging.warning(f'SVSync: data failed to validate')
            except Exception as e:
                logging.warning(f'SVSync: unknown error has occured: {e}')

            retries = retries - 1
            if retries+1 > 0:
                logging.warning(f'SVSync: retrying fetching data')
        return None
    def getDataName(self, nid:Name, seqNum:int) -> Name:
        return ( self.groupPrefix + [Component.from_str("d")] + nid + Name.from_str("/epoch-"+str(seqNum)) )