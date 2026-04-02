Option Explicit

' Column numbers (1-based) — auto-set by sheet.py, do NOT change manually
Private Const COL_PLOT_ID      As Long = 1
Private Const COL_PROJ_DATE    As Long = 12
Private Const COL_ALLOC_STATUS As Long = 16

' ============================================================
' CASCADE RULE
' When any cell in the Projected Date column is edited:
'   1. Note the old date (via Undo/Redo trick).
'   2. Compute gap = new date - old date.
'   3. Find all rows on the SAME plot that:
'        a) have Allocation Status = "Pending"   (unallocated only)
'        b) have Projected Date >= new date      (future only)
'   4. Shift their Projected Date by gap days.
' Allocated rows are NEVER touched.
' ============================================================

Private Sub Worksheet_Change(ByVal Target As Range)

    ' Only react to single-cell edits in the Projected Date column
    If Target.CountLarge > 1 Then Exit Sub
    If Target.Column <> COL_PROJ_DATE Then Exit Sub
    If Target.Row < 2 Then Exit Sub

    Dim newDate As Variant
    newDate = Target.Value
    If Not IsDate(newDate) Then Exit Sub

    ' --- Get the OLD date via Undo / Redo ---
    Application.EnableEvents = False
    Application.Undo
    Dim oldVal As Variant
    oldVal = Target.Value
    Application.Redo
    Application.EnableEvents = True

    If Not IsDate(oldVal) Then Exit Sub

    Dim gapDays As Long
    gapDays = CLng(CDbl(CDate(newDate)) - CDbl(CDate(oldVal)))
    If gapDays = 0 Then Exit Sub

    ' --- Which plot does this row belong to? ---
    Dim plotID As Variant
    plotID = Me.Cells(Target.Row, COL_PLOT_ID).Value
    If IsEmpty(plotID) Or Trim(CStr(plotID)) = "" Then Exit Sub

    ' --- Disable events/screen/calc for performance ---
    Application.EnableEvents = False
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    Dim lastRow As Long
    lastRow = Me.Cells(Me.Rows.Count, COL_PLOT_ID).End(xlUp).Row

    Dim r As Long
    For r = 2 To lastRow
        If r = Target.Row Then GoTo NextRow

        ' Same plot?
        If CStr(Me.Cells(r, COL_PLOT_ID).Value) <> CStr(plotID) Then GoTo NextRow

        ' Pending (unallocated) only?
        Dim st As String
        st = Trim(LCase(CStr(Me.Cells(r, COL_ALLOC_STATUS).Value)))
        If st <> "pending" Then GoTo NextRow

        ' Future date only (>= the new date we just set)?
        Dim rv As Variant
        rv = Me.Cells(r, COL_PROJ_DATE).Value
        If Not IsDate(rv) Then GoTo NextRow
        If CDbl(CDate(rv)) < CDbl(CDate(newDate)) Then GoTo NextRow

        ' Shift
        Dim shifted As Date
        shifted = CDate(rv) + gapDays
        With Me.Cells(r, COL_PROJ_DATE)
            .Value = shifted
            .NumberFormat = "DD-MMM-YYYY"
        End With

NextRow:
    Next r

    Application.EnableEvents = True
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic

End Sub
