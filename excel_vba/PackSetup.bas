Attribute VB_Name = "PackSetup"
Option Explicit
'==============================================================================
' One-time setup: adds "Run monthly pack" and "Export ERP price list" buttons
' to the README sheet. Run once after importing the modules, then save as .xlsm.
'==============================================================================

Public Sub AddButtons()
    Dim ws As Worksheet, b As Object
    Set ws = ThisWorkbook.Worksheets("README")
    For Each b In ws.Buttons
        b.Delete
    Next b
    AddOne ws, "Run monthly pack", "MonthlyPack.RunMonthlyPack", ws.Range("D2")
    AddOne ws, "Pack + Outlook draft", "MonthlyPack.RunMonthlyPackAndDraftEmail", ws.Range("D4")
    AddOne ws, "Export ERP price list", "PriceListExport.ExportERPPriceList", ws.Range("D6")
End Sub

Private Sub AddOne(ByVal ws As Worksheet, ByVal caption As String, ByVal macro As String, ByVal anchor As Range)
    Dim b As Object
    Set b = ws.Buttons.Add(anchor.Left, anchor.Top, 170, 26)
    b.Caption = caption
    b.OnAction = macro
End Sub
