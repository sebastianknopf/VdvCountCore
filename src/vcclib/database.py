import sqlobject

from vcclib.model import Stop
from vcclib.model import Line
from vcclib.model import Trip
from vcclib.model import StopTime
from vcclib.model import MasterDataVehicle
from vcclib.model import MasterDataObjectClass

def init():
    sqlobject.sqlhub.processConnection = sqlobject.connectionForURI('mysql://vccuser:vccpasswd@vcc-database/vccdb')

    Stop.createTable(ifNotExists=True)
    Line.createTable(ifNotExists=True)
    Trip.createTable(ifNotExists=True)
    StopTime.createTable(ifNotExists=True)

    MasterDataVehicle.createTable(ifNotExists=True)
    MasterDataObjectClass.createTable(ifNotExists=True)

def connection():
    return sqlobject.sqlhub.processConnection