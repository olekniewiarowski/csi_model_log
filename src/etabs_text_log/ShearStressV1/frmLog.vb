Imports System
Imports System.Collections.Generic
Imports System.IO   ' CHANGE: Added for file export
Imports System.Linq
Imports System.Security.AccessControl
Imports System.Text ' Used for the debug log
Imports System.Windows.Forms
Imports CSI_COMPARE.frmViewLog
Imports ETABSv1

Public Class frmLog
    Private debugLog As New StringBuilder()
    Private mySapModel As cSapModel
    Private myPluginCallback As cPluginCallback
    Private selectedLogDirectory As String = String.Empty

    ' Add this public subroutine to receive the objects when the form is created


    Public Sub setSapModel(ByRef SapModel As cSapModel, ByRef ISapPlugin As cPluginCallback)
        mySapModel = SapModel
        myPluginCallback = ISapPlugin
    End Sub

    Public Sub setParentPluginObject(ByRef parent As Object)
        ' This can be used for more advanced communication if needed but is not used here.
    End Sub

    Private Sub LogMessage(message As String)
        debugLog.AppendLine(message)
        txtLog.Text = debugLog.ToString()
        txtLog.SelectionStart = txtLog.Text.Length
        txtLog.ScrollToCaret()
        Application.DoEvents() ' Force UI update
    End Sub



    Private Sub Form1_FormClosing(sender As Object, e As FormClosingEventArgs) Handles Me.FormClosing
        Try
            ' A return value of 0 indicates a successful, clean exit.
            myPluginCallback.Finish(0)
        Catch ex As Exception
            ' Handle any errors during shutdown, though it's rare.
        End Try
    End Sub



    Private Sub lblTitle_Click(sender As Object, e As EventArgs)

    End Sub

    Private Sub btnLog_Click(sender As Object, e As EventArgs) Handles btnLog.Click
        LogMessage("LOG button pressed. Starting E2K export process...")

        Try
            ' 1. Get the current model's full file path
            Dim modelPath As String = mySapModel.GetModelFilename(True) ' Returns the full path if model is saved

            If String.IsNullOrEmpty(modelPath) OrElse modelPath = "No file open" Then
                LogMessage("ERROR: Model must be saved and open to export E2K.")
                MessageBox.Show("Please save your ETABS model before using the LOG button.", "Export Error", MessageBoxButtons.OK, MessageBoxIcon.Error)
                Return
            End If

            ' 2. Extract the directory and the model name without extension
            Dim modelDirectory As String = Path.GetDirectoryName(modelPath)
            Dim modelFileNameWithoutExt As String = Path.GetFileNameWithoutExtension(modelPath)

            ' 3. Generate the formatted timestamp
            ' Format: yyyyMMdd_HHmmss (e.g., 20251115_154026)
            Dim timeStamp As String = DateTime.Now.ToString("yyyyMMdd_HHmmss")

            Dim exportDirectory As String
            If Not String.IsNullOrEmpty(selectedLogDirectory) Then
                exportDirectory = selectedLogDirectory
            Else
                exportDirectory = modelDirectory ' Fallback to model's directory
            End If

            ' Ensure the target directory exists (important if the path was manually entered or if the script is run on a new machine)
            If Not Directory.Exists(exportDirectory) Then
                Directory.CreateDirectory(exportDirectory)
            End If

            ' 4. Construct the full path for the new E2K file
            Dim newE2KFileName As String = $"{modelFileNameWithoutExt}_{timeStamp}.e2k"
            Dim exportPath As String = Path.Combine(exportDirectory, newE2KFileName)

            LogMessage($"Exporting to: {exportPath}")

            ' 5. Call the ETABS API to export the E2K file
            ' The ExportE2K method requires a full path and an optional flag (set to 0 for no changes)
            Dim ret As Integer = mySapModel.File.ExportFile(exportPath, eFileTypeIO.TextFile)

            If ret = 0 Then
                LogMessage("SUCCESS: E2K text file exported successfully.")
                MessageBox.Show($"E2K file exported to:{Environment.NewLine}{exportPath}", "Export Complete", MessageBoxButtons.OK, MessageBoxIcon.Information)
            Else
                LogMessage($"ERROR: E2K export failed with return code {ret}.")
                MessageBox.Show($"The E2K export failed. ETABS API returned code: {ret}", "Export Failed", MessageBoxButtons.OK, MessageBoxIcon.Error)
            End If

        Catch ex As Exception
            LogMessage($"CRITICAL ERROR: An unexpected error occurred during export: {ex.Message}")
            MessageBox.Show($"A critical error occurred: {ex.Message}", "Critical Error", MessageBoxButtons.OK, MessageBoxIcon.Stop)
        End Try
    End Sub

    Private Sub btnViewLog_Click(sender As Object, e As EventArgs) Handles btnViewLog.Click
        LogMessage("VIEW LOG button pressed. Attempting to read Model Log...")

        Try
            Dim modelPath As String = mySapModel.GetModelFilename(True)
            If String.IsNullOrEmpty(modelPath) OrElse modelPath = "No file open" Then Return

            Dim modelDirectory As String = Path.GetDirectoryName(modelPath)
            ' 1. Create the viewer form
            Dim logViewerForm As New frmViewLog()

            Dim exportDirectory As String
            If Not String.IsNullOrEmpty(selectedLogDirectory) Then
                exportDirectory = selectedLogDirectory
            Else
                exportDirectory = modelDirectory ' Fallback to model's directory
            End If

            ' Ensure the target directory exists (important if the path was manually entered or if the script is run on a new machine)
            If Not Directory.Exists(exportDirectory) Then
                Directory.CreateDirectory(exportDirectory)
            End If

            ' 2. Pass the directory path to the new function name (ParseLogFiles)
            Dim logEntries As List(Of LogEntry) = logViewerForm.ParseLogFiles(exportDirectory)

            ' 3. Load the timeline display
            logViewerForm.LoadTimeline(logEntries)

            If logEntries.Count = 0 Then
                LogMessage("WARNING: No log files (Model Log_V*.txt) found in directory.")
            End If

            logViewerForm.Text = $"Version Log for {Path.GetFileNameWithoutExtension(modelPath)}"
            logViewerForm.Show()

        Catch ex As Exception
            LogMessage($"CRITICAL ERROR: Failed to view log: {ex.Message}")
            MessageBox.Show($"A critical error occurred while trying to view the log: {ex.Message}", "Critical Error", MessageBoxButtons.OK, MessageBoxIcon.Stop)
        End Try
    End Sub

    Public Sub RunPythonScript(ByVal targetDirectory As String)
        Dim pythonEnvName As String = "csicompare"
        Dim scriptDir As String = "C:\Users\alahri\Desktop\CSI_Compare\Python_Scripts"

        ' 1. Construct the sequence of commands to run in cmd.exe
        '    a. Initialize Conda (assuming Miniforge is in the system PATH, if not, use full path to conda.exe)
        '    b. Activate the environment (csicompare)
        '    c. Change directory to the script location (where main.py is)
        '    d. Execute the Python module, passing the target directory in quotes.

        Dim cdToScript As String = "cd /D " & Chr(34) & scriptDir & Chr(34) ' /D changes drive as well
        Dim pyCommand As String = "python -m main " & Chr(34) & targetDirectory & Chr(34) ' Pass the required target_dir

        ' Combine all commands using the & character, and enclose them in parentheses
        ' Note: cmd /k keeps the window open; cmd /c closes it after execution. Use /c for non-interactive plugin use.
        Dim cmd As String = $"cmd /k ""{cdToScript} & {pyCommand}"""

        LogMessage($"Executing command: {cmd}")

        ' Use Shell to execute the complex command line
        Shell(cmd, vbNormalFocus)

        ' Note: This launch is non-blocking. The script runs in the background.
        LogMessage("Python script launched (asynchronous). Check console/log for completion.")
    End Sub
    Private Sub btnRunLLM_Click(sender As Object, e As EventArgs) Handles btnRunLLM.Click
        LogMessage("LLM button pressed. Determining target directory...")

        ' *** You must define this directory based on your selectedLogDirectory or modelDirectory ***
        Dim targetDir As String = "C:\Users\alahri\Desktop\CSI_Compare\Python_Scripts\versions"

        If Not String.IsNullOrEmpty(selectedLogDirectory) Then
            targetDir = selectedLogDirectory
        Else
            ' Fallback to model directory
            Dim modelPath As String = mySapModel.GetModelFilename(True)
            If Not String.IsNullOrEmpty(modelPath) AndAlso modelPath <> "No file open" Then
                targetDir = Path.GetDirectoryName(modelPath)
            Else
                MessageBox.Show("Please save the ETABS model and select a log directory first.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error)
                Return
            End If
        End If

        LogMessage($"Target Directory for LLM: {targetDir}")

        ' Call the updated function with the required directory path
        RunPythonScript(targetDir)

    End Sub

    Private Sub btnSelectLogDirectory_Click(sender As Object, e As EventArgs) Handles btnSelectLogDirectory.Click
        LogMessage("Selecting new log directory...")

        Using folderBrowser As New FolderBrowserDialog()
            folderBrowser.Description = "Select a folder to save E2K and Model Log files."

            ' --- FIX: Use SelectedPath to set the initial location ---
            If Not String.IsNullOrEmpty(selectedLogDirectory) Then
                ' If a directory has been selected previously, use it
                folderBrowser.SelectedPath = selectedLogDirectory
            Else
                Try
                    ' If no directory is selected, try to default to the current model's directory
                    Dim modelPath As String = mySapModel.GetModelFilename(True)
                    If Not String.IsNullOrEmpty(modelPath) AndAlso modelPath <> "No file open" Then
                        folderBrowser.SelectedPath = Path.GetDirectoryName(modelPath)
                    End If
                Catch ex As Exception
                    ' Ignore if model path fails
                End Try
            End If
            ' --------------------------------------------------------


            If folderBrowser.ShowDialog() = DialogResult.OK Then
                selectedLogDirectory = folderBrowser.SelectedPath
                LogMessage($"SUCCESS: Log directory set to: {selectedLogDirectory}")

                ' Optional: Update a label on your form (e.g., lblLogPath.Text) 
                ' lblLogPath.Text = selectedLogDirectory 
            Else
                LogMessage("Directory selection cancelled.")
            End If
        End Using
    End Sub
End Class