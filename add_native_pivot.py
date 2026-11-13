"""Add a native Excel PivotTable (LibreOffice UNO). Usage: python add_native_pivot.py in.xlsx out.xlsx"""

import sys
import time
import subprocess
import os
import tempfile
import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.table import CellAddress, CellRangeAddress


def get_soffice_env():
    env = os.environ.copy()
    env["SAL_USE_VCLPLUGIN"] = "svp"
    return env


src, dst = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
prof = tempfile.mkdtemp(prefix="lo_prof_")
p = subprocess.Popen(
    [
        "soffice",
        f"-env:UserInstallation=file://{prof}",
        "--headless",
        "--invisible",
        "--norestore",
        "--accept=socket,host=127.0.0.1,port=2002;urp;",
    ],
    env=get_soffice_env(),
)
local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
for _ in range(60):
    try:
        ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
        break
    except Exception:
        time.sleep(1)
smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)


def pv(n, v):
    x = PropertyValue()
    x.Name = n
    x.Value = v
    return x


doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(src), "_blank", 0, (pv("Hidden", True),))
sheets = doc.Sheets
data = sheets.getByName("Data_Weekly")
cur = data.createCursor()
cur.gotoEndOfUsedArea(False)
last_row, last_col = cur.RangeAddress.EndRow, cur.RangeAddress.EndColumn
sheets.insertNewByName("PivotTable_Price", 4)
pt_sheet = sheets.getByName("PivotTable_Price")
pt_sheet.getCellByPosition(
    0, 0
).String = "Native PivotTable: average CAD price per case by item (rows) and year (columns). Source: Data_Weekly. Refresh in Excel after editing data."
tables = pt_sheet.getDataPilotTables()
desc = tables.createDataPilotDescriptor()
rng = CellRangeAddress()
rng.Sheet = 2
rng.StartColumn = 0
rng.StartRow = 0
rng.EndColumn = last_col
rng.EndRow = last_row
# find Data_Weekly index
for i in range(sheets.Count):
    if sheets.getByIndex(i).Name == "Data_Weekly":
        rng.Sheet = i
desc.setSourceRange(rng)
from com.sun.star.sheet.DataPilotFieldOrientation import ROW, COLUMN, DATA
from com.sun.star.sheet.GeneralFunction import AVERAGE

fields = desc.getDataPilotFields()


def field(name):
    for i in range(fields.Count):
        f = fields.getByIndex(i)
        if f.Name == name:
            return f


field("Item").Orientation = ROW
field("Year").Orientation = COLUMN
f = field("Price CAD/case")
f.Orientation = DATA
f.Function = AVERAGE
dest = CellAddress()
dest.Sheet = [i for i in range(sheets.Count) if sheets.getByIndex(i).Name == "PivotTable_Price"][0]
dest.Column = 0
dest.Row = 2
tables.insertNewByName("PricePivot", dest, desc)
doc.storeToURL(uno.systemPathToFileUrl(dst), (pv("FilterName", "Calc MS Excel 2007 XML"),))
doc.close(True)
try:
    desktop.terminate()
except Exception:
    pass
p.wait(timeout=30)
print("ok", last_row, last_col)
