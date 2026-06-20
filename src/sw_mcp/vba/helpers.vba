' ============================================================
' Verified helper library (ported verbatim from the solidworks-vba skill's
' core-patterns.md). These ran successfully on the user's SolidWorks 2022.
' Plane/sketch selection is by TREE POSITION, never by name string.
' ============================================================

' IMPORTANT (on-the-fly .swb quirk): API VARIANT_BOOL returns arrive as +1
' here, not VBA's True (-1). VBA's "Not" is bitwise, so callers must test these
' booleans with "= False", NEVER "If Not x". Object checks ("Is Nothing") are
' fine. Functions below return the raw API result; the generators compare to
' False at the call site.
Function SelectStdPlane(ByVal planeIndex As Long, _
    ByVal appendSel As Boolean, ByVal markValue As Long) As Boolean
    ' 1=Front, 2=Top, 3=Right (creation order in every standard template).
    Dim feat As SldWorks.Feature
    Dim nFound As Long
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "RefPlane" Then
            nFound = nFound + 1
            If nFound = planeIndex Then
                SelectStdPlane = feat.Select2(appendSel, markValue)
                Exit Function
            End If
        End If
        Set feat = feat.GetNextFeature
    Loop
    SelectStdPlane = False
End Function

Function SelectLatestSketch() As Boolean
    Dim feat As SldWorks.Feature
    Dim lastSketchName As String
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "ProfileFeature" Then lastSketchName = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    If lastSketchName = "" Then
        SelectLatestSketch = False
        Exit Function
    End If
    swModel.ClearSelection2 True
    SelectLatestSketch = swModelExt.SelectByID2(lastSketchName, "SKETCH", 0, 0, 0, False, 0, Nothing, swSelectOption_e.swSelectOptionDefault)
End Function

Function FindFeatureNameByType(ByVal typeKeyword As String) As String
    Dim feat As SldWorks.Feature
    Dim resultName As String
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If InStr(1, feat.GetTypeName2, typeKeyword, vbTextCompare) > 0 Then resultName = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    FindFeatureNameByType = resultName
End Function

Function FindFeatureByName(ByVal nm As String) As SldWorks.Feature
    Dim f As SldWorks.Feature
    Set f = swModel.FirstFeature
    Do While Not f Is Nothing
        If f.Name = nm Then Set FindFeatureByName = f: Exit Function
        Set f = f.GetNextFeature
    Loop
    Set FindFeatureByName = Nothing
End Function

Function FindLastSketchName() As String
    FindLastSketchName = FindFeatureNameByType("ProfileFeature")
End Function

Function FindLastRefPlaneName() As String
    FindLastRefPlaneName = FindFeatureNameByType("RefPlane")
End Function

Sub RenameFeature(ByVal oldNm As String, ByVal newNm As String)
    Dim f As SldWorks.Feature
    If Len(oldNm) = 0 Then Exit Sub
    Set f = FindFeatureByName(oldNm)
    If Not f Is Nothing Then f.Name = newNm
End Sub

Function FindLastFeature() As SldWorks.Feature
    ' The most-recently-added feature. Useful for surface methods that are Subs
    ' (void) or return Boolean and so do not hand back the new feature object.
    Dim f As SldWorks.Feature, lst As SldWorks.Feature
    Set f = swModel.FirstFeature
    Do While Not f Is Nothing
        Set lst = f
        Set f = f.GetNextFeature
    Loop
    Set FindLastFeature = lst
End Function

Function FindLastFeatureByType(ByVal token As String) As SldWorks.Feature
    ' Returns the LAST feature whose GetTypeName2 contains token (e.g. "Fillet",
    ' "Shell", "Rib", "Draft", "Cut", "Boss"). Robust when the API call does not
    ' return the feature object (InsertRib, InsertFeatureShell).
    Dim f As SldWorks.Feature, lst As SldWorks.Feature
    Set f = swModel.FirstFeature
    Do While Not f Is Nothing
        If InStr(1, f.GetTypeName2, token, vbTextCompare) > 0 Then Set lst = f
        Set f = f.GetNextFeature
    Loop
    Set FindLastFeatureByType = lst
End Function

Function FindCylindricalFace(ByVal targetR As Double) As SldWorks.Face2
    ' Locate a cylindrical face by radius - robust axis source for circular
    ' patterns and thread features.
    Dim swPart As SldWorks.PartDoc
    Dim vBodies As Variant, swBody As SldWorks.Body2
    Dim swFace As SldWorks.Face2, swSurf As SldWorks.Surface
    Dim cylParams As Variant
    Dim i As Long
    Set swPart = swModel
    vBodies = swPart.GetBodies2(swBodyType_e.swSolidBody, True)
    If IsEmpty(vBodies) Then Exit Function
    For i = 0 To UBound(vBodies)
        Set swBody = vBodies(i)
        Set swFace = swBody.GetFirstFace
        Do While Not swFace Is Nothing
            Set swSurf = swFace.GetSurface
            If swSurf.IsCylinder Then
                cylParams = swSurf.CylinderParams   ' origin xyz, axis xyz, radius
                If Abs(cylParams(6) - targetR) < 0.000001 Then
                    Set FindCylindricalFace = swFace
                    Exit Function
                End If
            End If
            Set swFace = swFace.GetNextFace
        Loop
    Next i
End Function

Function SelectFaceAt(ByVal x As Double, ByVal y As Double, ByVal z As Double, _
    ByVal append As Boolean, ByVal mark As Long) As Boolean
    SelectFaceAt = swModelExt.SelectByID2("", "FACE", x, y, z, append, mark, Nothing, 0)
End Function

Function SelectEdgeAt(ByVal x As Double, ByVal y As Double, ByVal z As Double, _
    ByVal append As Boolean, ByVal mark As Long) As Boolean
    SelectEdgeAt = swModelExt.SelectByID2("", "EDGE", x, y, z, append, mark, Nothing, 0)
End Function

' --- Silent diagnostics log (replaces blocking MsgBox in automated macros) ---
' The MCP server reads SWMCP_LOG_PATH after the run to get per-step status.
Sub SWMCP_Log(ByVal step As String, ByVal status As String, ByVal msg As String)
    Dim f As Integer
    On Error Resume Next
    f = FreeFile
    Open SWMCP_LOG_PATH For Append As #f
    Print #f, status & "|" & step & "|" & msg
    Close #f
    On Error GoTo 0
End Sub
