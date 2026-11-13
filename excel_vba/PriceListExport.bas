Attribute VB_Name = "PriceListExport"
Option Explicit
'==============================================================================
' Validates ERP_Price_List and writes the ERP bulk-import CSV.
' Rules: item_code and price_group filled, currency CAD, unit_price > 0,
' effective_from <= effective_to, one row per item_code x price_group, and a
' warning (not a block) when a price moves more than 15% in one week.
' Invalid rows are highlighted red and the CSV is not written.
'==============================================================================

Private Const SHEET_NAME As String = "ERP_Price_List"
Private Const HEADER_ROW As Long = 4
Private Const EXPORT_COLS As Long = 12          ' A:L = item_code ... reason
Private Const BIG_MOVE As Double = 0.15

Public Sub ExportERPPriceList()
    Dim ws As Worksheet, seen As Object, problems As Collection, warnings As Collection
    Dim r As Long, lastRow As Long, key As String, path As String

    Set ws = ThisWorkbook.Worksheets(SHEET_NAME)
    Set seen = CreateObject("Scripting.Dictionary")
    Set problems = New Collection
    Set warnings = New Collection
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row

    ws.Range(ws.Cells(HEADER_ROW + 1, 1), ws.Cells(lastRow, EXPORT_COLS)).Interior.ColorIndex = xlNone

    For r = HEADER_ROW + 1 To lastRow
        key = Trim$(CStr(ws.Cells(r, 1).Value)) & "|" & Trim$(CStr(ws.Cells(r, 4).Value))
        If Trim$(CStr(ws.Cells(r, 1).Value)) = "" Or Trim$(CStr(ws.Cells(r, 4).Value)) = "" Then
            Flag ws, r, problems, "missing item_code or price_group"
        ElseIf seen.Exists(key) Then
            Flag ws, r, problems, "duplicate of row " & seen(key)
        Else
            seen.Add key, r
        End If
        If CStr(ws.Cells(r, 6).Value) <> "CAD" Then Flag ws, r, problems, "currency is not CAD"
        If Not IsNumeric(ws.Cells(r, 7).Value) Or IsEmpty(ws.Cells(r, 7).Value) Then
            Flag ws, r, problems, "unit_price is not a number"
        ElseIf CDbl(ws.Cells(r, 7).Value) <= 0 Then
            Flag ws, r, problems, "unit_price must be above zero"
        ElseIf IsNumeric(ws.Cells(r, 8).Value) And Not IsEmpty(ws.Cells(r, 8).Value) Then
            If CDbl(ws.Cells(r, 8).Value) > 0 Then
                If Abs(CDbl(ws.Cells(r, 7).Value) / CDbl(ws.Cells(r, 8).Value) - 1) > BIG_MOVE Then
                    warnings.Add "Row " & r & " " & ws.Cells(r, 1).Value & "/" & ws.Cells(r, 4).Value & ": " & _
                                 Format$(CDbl(ws.Cells(r, 7).Value) / CDbl(ws.Cells(r, 8).Value) - 1, "+0%;-0%") & " vs prior"
                End If
            End If
        End If
        If CStr(ws.Cells(r, 10).Value) > CStr(ws.Cells(r, 11).Value) Then Flag ws, r, problems, "effective_from after effective_to"
    Next r

    If problems.Count > 0 Then
        ws.Activate
        MsgBox problems.Count & " problem(s); rows highlighted in red. First: " & problems(1), vbExclamation, "ERP price list"
        Exit Sub
    End If

    path = ThisWorkbook.Path & Application.PathSeparator & "ERP_price_upload_" & Format$(Now, "yyyy-mm-dd") & ".csv"
    WriteCsv ws, lastRow, path
    MonthlyPack.WriteLog "ERP CSV " & (lastRow - HEADER_ROW) & " rows, " & warnings.Count & " big moves", 0, path, 0
    If warnings.Count > 0 Then
        MsgBox "CSV written:" & vbCrLf & path & vbCrLf & vbCrLf & warnings.Count & " price(s) move more than " & _
               Format$(BIG_MOVE, "0%") & " this week; first: " & warnings(1), vbInformation, "ERP price list"
    Else
        MsgBox "CSV written:" & vbCrLf & path, vbInformation, "ERP price list"
    End If
End Sub

Private Sub Flag(ByVal ws As Worksheet, ByVal r As Long, ByVal problems As Collection, ByVal why As String)
    ws.Range(ws.Cells(r, 1), ws.Cells(r, EXPORT_COLS)).Interior.Color = RGB(255, 199, 206)
    problems.Add "row " & r & ": " & why
End Sub

Private Sub WriteCsv(ByVal ws As Worksheet, ByVal lastRow As Long, ByVal path As String)
    Dim f As Integer, r As Long, c As Long, line As String
    f = FreeFile
    Open path For Output As #f
    For r = HEADER_ROW To lastRow
        line = ""
        For c = 1 To EXPORT_COLS
            If c > 1 Then line = line & ","
            line = line & CsvField(ws.Cells(r, c).Value)
        Next c
        Print #f, line
    Next r
    Close #f
End Sub

Private Function CsvField(ByVal v As Variant) As String
    Dim s As String
    If IsNumeric(v) And Not IsEmpty(v) And VarType(v) <> vbString Then
        s = Trim$(Str$(v))                     ' locale-independent decimal point
    Else
        s = CStr(v)
    End If
    If InStr(s, ",") > 0 Or InStr(s, """") > 0 Then s = """" & Replace(s, """", """""") & """"
    CsvField = s
End Function
