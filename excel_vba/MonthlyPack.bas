Attribute VB_Name = "MonthlyPack"
Option Explicit
'==============================================================================
' Monthly margin pack for Margin_Variance_and_Terms.xlsx
'
' RunMonthlyPack: refresh -> recalculate -> run every reconciliation check ->
' rebuild the Pack_Summary sheet -> export a dated PDF -> append to Run_Log.
' If any check fails, nothing is exported and the failures are listed on
' Pack_Summary, so a broken number never leaves the building.
'
' Import: Developer > Visual Basic > File > Import File (all three .bas files),
' then save the workbook as .xlsm. Run PackSetup.AddButtons once for buttons.
'==============================================================================

Private Const HEADER_ROW As Long = 4          ' header row on every data sheet
Private Const CHECK_HEADER As String = "Check"
Private Const TOLERANCE As Double = 0.5       ' CAD; checks are rounded to the dollar
Private Const SUMMARY_SHEET As String = "Pack_Summary"
Private Const LOG_SHEET As String = "Run_Log"
Private Const PDF_SHEETS As String = "Pack_Summary,PVM_Bridge,Margin_Variance,Terms_Profitability"

Public Sub RunMonthlyPack()
    RunPack False
End Sub

Public Sub RunMonthlyPackAndDraftEmail()
    RunPack True
End Sub

Private Sub RunPack(ByVal draftEmail As Boolean)
    Dim failures As Collection
    Dim pdfPath As String
    Dim t0 As Double

    t0 = Timer
    On Error GoTo Fail
    SpeedUp True

    ThisWorkbook.RefreshAll                    ' Power Query / connections, if any
    Application.CalculateFull

    Set failures = ValidateChecks()
    BuildSummary failures
    Application.CalculateFull                  ' summary formulas were written under manual calc

    If failures.Count = 0 Then
        pdfPath = ExportPack()
        WriteLog "OK", 0, pdfPath, Timer - t0
        SpeedUp False
        ThisWorkbook.Worksheets(SUMMARY_SHEET).Activate
        If draftEmail Then DraftPackEmail pdfPath
        MsgBox "Monthly pack exported:" & vbCrLf & pdfPath, vbInformation, "Margin pack"
    Else
        WriteLog "BLOCKED", failures.Count, "", Timer - t0
        SpeedUp False
        ThisWorkbook.Worksheets(SUMMARY_SHEET).Activate
        MsgBox failures.Count & " check(s) failed, so the pack was not exported." & vbCrLf & _
               "The failing cells are listed on " & SUMMARY_SHEET & ".", vbExclamation, "Margin pack"
    End If
    Exit Sub

Fail:
    Dim msg As String
    msg = Err.Description
    SpeedUp False
    WriteLog "ERROR: " & msg, -1, "", Timer - t0
    MsgBox "The pack stopped: " & msg, vbCritical, "Margin pack"
End Sub

'------------------------------------------------------------------------------
' Every column headed "Check" (row 4) must be 0 within tolerance, every cell in
' column A that starts with "Check" must have 0 beside it, and no formula on
' any sheet may return an error (#REF!, #DIV/0!, ...).
'------------------------------------------------------------------------------
Public Function ValidateChecks() As Collection
    Dim failures As New Collection
    Dim ws As Worksheet, c As Range, hdr As Range, errCells As Range
    Dim r As Long, lastRow As Long, v As Variant

    For Each ws In ThisWorkbook.Worksheets
        If ws.Name <> SUMMARY_SHEET And ws.Name <> LOG_SHEET Then

            ' 1. Columns headed "Check"
            For Each hdr In ws.Range(ws.Cells(HEADER_ROW, 1), ws.Cells(HEADER_ROW, LastCol(ws))).Cells
                If CStr(hdr.Value) = CHECK_HEADER Then
                    lastRow = ws.Cells(ws.Rows.Count, hdr.Column).End(xlUp).Row
                    For r = HEADER_ROW + 1 To lastRow
                        v = ws.Cells(r, hdr.Column).Value
                        If Not IsCheckZero(v) Then failures.Add ws.Name & "!" & ws.Cells(r, hdr.Column).Address(False, False) & " = " & CStr(v)
                    Next r
                End If
            Next hdr

            ' 2. Labelled check cells, e.g. PVM_Bridge "Check (GM 2023 - GM 2019 - effects)"
            lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
            For r = HEADER_ROW + 1 To lastRow
                If Left$(CStr(ws.Cells(r, 1).Value), Len(CHECK_HEADER)) = CHECK_HEADER Then
                    v = ws.Cells(r, 2).Value
                    If Not IsCheckZero(v) Then failures.Add ws.Name & "!" & ws.Cells(r, 2).Address(False, False) & " = " & CStr(v)
                End If
            Next r

            ' 3. Formula errors anywhere on the sheet
            Set errCells = Nothing
            On Error Resume Next
            Set errCells = ws.UsedRange.SpecialCells(xlCellTypeFormulas, xlErrors)
            On Error GoTo 0
            If Not errCells Is Nothing Then
                For Each c In errCells.Cells
                    failures.Add ws.Name & "!" & c.Address(False, False) & " returns " & c.Text
                Next c
            End If
        End If
    Next ws
    Set ValidateChecks = failures
End Function

Private Function IsCheckZero(ByVal v As Variant) As Boolean
    If IsError(v) Then
        IsCheckZero = False
    ElseIf IsEmpty(v) Then
        IsCheckZero = True
    ElseIf IsNumeric(v) Then
        IsCheckZero = Abs(CDbl(v)) <= TOLERANCE
    Else
        IsCheckZero = False
    End If
End Function

'------------------------------------------------------------------------------
' Pack_Summary: live formulas into the model, so the page stays correct if
' someone edits an input after the run. Only the run stamp and check list are
' static text.
'------------------------------------------------------------------------------
Public Sub BuildSummary(ByVal failures As Collection)
    Dim ws As Worksheet, r As Long, i As Long

    Set ws = GetOrCreateSheet(SUMMARY_SHEET, True)
    ws.Cells.Clear

    ws.Range("A1").Value = "Monthly margin pack"
    ws.Range("A1").Font.Size = 14
    ws.Range("A1").Font.Bold = True
    ws.Range("A2").Value = "Run " & Format$(Now, "yyyy-mm-dd hh:nn") & " by " & Application.UserName & _
                           ". Costs are real Toronto terminal prices; volumes and promotions are synthetic."
    ws.Range("A2").Font.Italic = True

    r = 4
    SectionHeader ws, r, "Margin against target, all months"
    KPI ws, r + 1, "Revenue", "=Margin_Variance!B70", "$#,##0"
    KPI ws, r + 2, "Gross margin", "=Margin_Variance!C70", "$#,##0"
    KPI ws, r + 3, "GM %", "=Margin_Variance!C70/Margin_Variance!B70", "0.0%"
    KPI ws, r + 4, "Variance to target", "=Margin_Variance!E70", "$#,##0;($#,##0)"
    KPI ws, r + 5, "  of which cost timing", "=Margin_Variance!F70", "$#,##0;($#,##0)"
    KPI ws, r + 6, "  of which price hold", "=Margin_Variance!G70", "$#,##0;($#,##0)"
    KPI ws, r + 7, "Worst month", _
        "=INDEX(Margin_Variance!A5:A69,MATCH(MIN(Margin_Variance!E5:E69),Margin_Variance!E5:E69,0))", "@"
    KPI ws, r + 8, "Worst month variance", "=MIN(Margin_Variance!E5:E69)", "$#,##0;($#,##0)"

    r = 14
    SectionHeader ws, r, "Gross margin bridge, 2019 to 2023"
    For i = 0 To 6
        KPI ws, r + 1 + i, "=PVM_Bridge!A" & (5 + i), "=PVM_Bridge!B" & (5 + i), "$#,##0;($#,##0)"
    Next i

    r = 23
    SectionHeader ws, r, "Customer terms"
    For i = 0 To 3
        KPI ws, r + 1 + i, "=Terms_Profitability!A" & (5 + i), "=Terms_Profitability!M" & (5 + i), "0.0%"
    Next i
    ws.Range("C" & (r + 1)).Value = "share of weeks >10 pts under target"

    r = 29
    SectionHeader ws, r, "Reconciliation checks"
    If failures.Count = 0 Then
        ws.Cells(r + 1, 1).Value = "All checks pass (every Check column is 0, no formula errors)."
        ws.Cells(r + 1, 1).Font.Color = RGB(0, 128, 0)
    Else
        ws.Cells(r + 1, 1).Value = failures.Count & " check(s) failed. The pack was not exported:"
        ws.Cells(r + 1, 1).Font.Color = RGB(192, 0, 0)
        For i = 1 To failures.Count
            ws.Cells(r + 1 + i, 1).Value = "  " & failures(i)
        Next i
    End If

    ws.Columns("A").ColumnWidth = 34
    ws.Columns("B").ColumnWidth = 16
    ws.Columns("C").ColumnWidth = 36
    With ws.PageSetup
        .Orientation = xlPortrait
        .Zoom = False
        .FitToPagesWide = 1
        .FitToPagesTall = 1
    End With
End Sub

Private Sub SectionHeader(ByVal ws As Worksheet, ByVal r As Long, ByVal title As String)
    With ws.Range(ws.Cells(r, 1), ws.Cells(r, 2))
        .Interior.Color = RGB(31, 56, 100)
        .Font.Color = RGB(255, 255, 255)
        .Font.Bold = True
    End With
    ws.Cells(r, 1).Value = title
End Sub

Private Sub KPI(ByVal ws As Worksheet, ByVal r As Long, ByVal label As String, ByVal formula As String, ByVal fmt As String)
    If Left$(label, 1) = "=" Then ws.Cells(r, 1).Formula = label Else ws.Cells(r, 1).Value = label
    ws.Cells(r, 2).Formula = formula
    ws.Cells(r, 2).NumberFormat = fmt
    ws.Cells(r, 2).HorizontalAlignment = xlRight
End Sub

'------------------------------------------------------------------------------
' PDF of the summary, bridge, variance and terms sheets in <workbook folder>\reports
'------------------------------------------------------------------------------
Public Function ExportPack() As String
    Dim folder As String, path As String, names As Variant, i As Long

    folder = ThisWorkbook.Path & Application.PathSeparator & "reports"
    If Dir(folder, vbDirectory) = "" Then MkDir folder
    path = folder & Application.PathSeparator & "Margin_Pack_" & Format$(Now, "yyyy-mm-dd_hhnn") & ".pdf"

    names = Split(PDF_SHEETS, ",")
    For i = LBound(names) To UBound(names)
        With ThisWorkbook.Worksheets(names(i)).PageSetup
            .Orientation = xlLandscape
            .Zoom = False
            .FitToPagesWide = 1
            .FitToPagesTall = False
        End With
    Next i

    ThisWorkbook.Worksheets(names).Select
    ActiveSheet.ExportAsFixedFormat Type:=xlTypePDF, Filename:=path, _
        Quality:=xlQualityStandard, IncludeDocProperties:=True, IgnorePrintAreas:=False, OpenAfterPublish:=False
    ThisWorkbook.Worksheets(SUMMARY_SHEET).Select
    ExportPack = path
End Function

'------------------------------------------------------------------------------
' Opens (never sends) an Outlook draft with the PDF attached. Late-bound, so
' the workbook needs no Outlook reference and still opens where Outlook is absent.
'------------------------------------------------------------------------------
Public Sub DraftPackEmail(ByVal pdfPath As String)
    Dim ol As Object, mail As Object
    On Error Resume Next
    Set ol = CreateObject("Outlook.Application")
    On Error GoTo 0
    If ol Is Nothing Then
        MsgBox "Outlook is not available. The PDF is at:" & vbCrLf & pdfPath, vbInformation, "Margin pack"
        Exit Sub
    End If
    Set mail = ol.CreateItem(0)
    With mail
        .Subject = "Monthly margin pack - " & Format$(Date, "mmmm yyyy")
        .Body = "Hi," & vbCrLf & vbCrLf & _
                "Attached is this month's margin pack: margin against target, the 2019-2023 gross margin bridge " & _
                "and customer terms. All reconciliation checks passed." & vbCrLf & vbCrLf & "Thanks"
        .Attachments.Add pdfPath
        .Display
    End With
End Sub

'------------------------------------------------------------------------------
' Helpers
'------------------------------------------------------------------------------
Public Sub WriteLog(ByVal status As String, ByVal failedChecks As Long, ByVal output As String, ByVal seconds As Double)
    Dim ws As Worksheet, r As Long
    Set ws = GetOrCreateSheet(LOG_SHEET, False)
    If ws.Range("A1").Value = "" Then
        ws.Range("A1:F1").Value = Array("Timestamp", "User", "Status", "Failed checks", "Output", "Seconds")
        ws.Range("A1:F1").Font.Bold = True
        ws.Columns("A").ColumnWidth = 18
        ws.Columns("E").ColumnWidth = 60
    End If
    r = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row + 1
    ws.Cells(r, 1).Value = Now
    ws.Cells(r, 1).NumberFormat = "yyyy-mm-dd hh:mm"
    ws.Cells(r, 2).Value = Application.UserName
    ws.Cells(r, 3).Value = status
    ws.Cells(r, 4).Value = failedChecks
    ws.Cells(r, 5).Value = output
    ws.Cells(r, 6).Value = Round(seconds, 1)
End Sub

Public Function GetOrCreateSheet(ByVal sheetName As String, ByVal first As Boolean) As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(sheetName)
    On Error GoTo 0
    If ws Is Nothing Then
        If first Then
            Set ws = ThisWorkbook.Worksheets.Add(Before:=ThisWorkbook.Worksheets(1))
        Else
            Set ws = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Worksheets(ThisWorkbook.Worksheets.Count))
        End If
        ws.Name = sheetName
    End If
    Set GetOrCreateSheet = ws
End Function

Private Function LastCol(ByVal ws As Worksheet) As Long
    LastCol = ws.Cells(HEADER_ROW, ws.Columns.Count).End(xlToLeft).Column
End Function

Private Sub SpeedUp(ByVal turnOn As Boolean)
    Application.ScreenUpdating = Not turnOn
    Application.EnableEvents = Not turnOn
    Application.DisplayAlerts = Not turnOn
    If turnOn Then Application.Calculation = xlCalculationManual Else Application.Calculation = xlCalculationAutomatic
End Sub
