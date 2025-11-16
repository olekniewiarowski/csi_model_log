Imports CSiAPIv1
Imports ETABSv1
Imports Microsoft.SqlServer.Server
Public Class cPlugin

    Private Shared modality As String = "Non-Modal"

    Friend Shared VersionString As String = "Version " _
                                            & System.Reflection.Assembly.GetExecutingAssembly.GetName().Version.ToString _
                                            & " , .NET Only , Compiled as " _
                                            & System.Reflection.Assembly.GetExecutingAssembly.GetName().ProcessorArchitecture.ToString _
                                            & " , " & modality

    Public Function Info(ByRef Text As String) As Integer

        Try
            Text = "This external Plugin is supplied by Computers and Structures, Inc., "
            Text = Text & "as a simple example for developers of new Plugins for ETABS. "
            Text = Text & "It starts a new model, then converts a line of text into "
            Text = Text & "frame objects and adds them your model. If you enter the "
            Text = Text & "text ""crash"", an error will be generated for testing purposes. "
            Text &= VersionString
        Catch ex As Exception
        End Try

        Return 0

    End Function

    Public Sub Main(ByRef SapModel As cSapModel, ByRef ISapPlugin As cPluginCallback)

        Dim aForm As New frmLog

        Try
            aForm.setParentPluginObject(Me)
            aForm.setSapModel(SapModel, ISapPlugin)

            If StrComp(modality, "Non-Modal", CompareMethod.Text) = 0 Then
                ' Non-modal form, allows graphics refresh operations in CSI program, 
                ' but Main will return to CSI program before the form is closed.
                aForm.Show()
            Else
                ' Modal form, will not return to CSI program until form is closed,
                ' but may cause errors when refreshing the view.
                aForm.ShowDialog()
            End If

            ' It is very important to call ISapPlugin.Finish(iError) when form closes, !!!
            ' otherwise, CSI program will wait and be hung !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            ' this must be done inside the closing event for the form itself, not here !!!

            ' if you simply have algorithmic code here without any forms, 
            ' then call ISapPlugin.Finish(iError) here before returning to CSI program

            ' if your code will run for more than a few seconds, you should exercise
            ' the Windows messaging loop to keep the program responsive. You may 
            ' also want to provide an opportunity for the user to cancel operations.

        Catch ex As Exception
            MsgBox("The following error terminated the Plugin:" & vbCrLf & ex.Message)

            ' call Finish to inform CSI program that the PlugIn has terminated
            Try
                ISapPlugin.Finish(1)
            Catch ex1 As Exception
            End Try
        End Try

        Return

    End Sub

    Protected Overrides Sub Finalize()
        MyBase.Finalize()
    End Sub
End Class
