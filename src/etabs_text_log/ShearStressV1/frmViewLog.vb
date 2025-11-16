Imports System.Drawing
Imports System.Drawing.Drawing2D
Imports System.IO
Imports System.Text.RegularExpressions
Imports System.Windows.Forms

Public Class frmViewLog

    ' Method to set the content of the log viewer.
    'Public Sub LoadLogContent(ByVal logText As String)
    'txtLogContent.Text = logText
    ' Optional: Make the log content read-only
    'txtLogContent.ReadOnly = True
    'End Sub

    Public Class LogEntry
        Public Property FileTime As DateTime
        Public Property VersionFileName As String
        Public Property ComparedAgainst As String
        Public Property HighLevelSummary As String
        Public Property FullDetails As String
        Public Property IsCurrent As Boolean = False
    End Class



    Public Function ParseLogFiles(ByVal directoryPath As String) As List(Of LogEntry)
        Dim logEntries As New List(Of LogEntry)()
        Dim directoryPath1 As String
        ' 1. Find all log files starting with "Model Log_V"
        directoryPath1 = directoryPath + "\Summary"
        Dim logFilePaths As String() = Directory.GetFiles(directoryPath1, "*_summary.txt")

        If logFilePaths.Length = 0 Then
            Return logEntries
        End If

        ' 2. Process each file independently
        For Each logFilePath As String In logFilePaths

            Dim logContent As String = File.ReadAllText(logFilePath)
            Dim logEntry As New LogEntry()

            Try
                ' A. Extract High-Level Metadata (## tags)
                Dim regexTemplate As String = "## {0}:\s*(.*)"

                Dim comparedModelMatch As Match = Regex.Match(logContent, String.Format(regexTemplate, "Compared Model"))
                'Dim timeStampMatch As Match = Regex.Match(logContent, String.Format(regexTemplate, "Time Stamp"))
                Dim baseModelMatch As Match = Regex.Match(logContent, String.Format(regexTemplate, "Base Model"))

                If comparedModelMatch.Success Then logEntry.VersionFileName = comparedModelMatch.Groups(1).Value.Trim()
                If baseModelMatch.Success Then logEntry.ComparedAgainst = baseModelMatch.Groups(1).Value.Trim()
                'If timeStampMatch.Success Then DateTime.TryParse(timeStampMatch.Groups(1).Value, logEntry.LogTime)

                ' B. Extract Key Changes (High-Level Summary)
                Dim keyChangesStartTag As String = "## Key Changes (high-level)"
                Dim detailedChangesStartTag As String = "### Detailed Changes"

                Dim keyChangesStartIndex As Integer = logContent.IndexOf(keyChangesStartTag) + keyChangesStartTag.Length
                Dim detailedChangesStartIndex As Integer = logContent.IndexOf(detailedChangesStartTag)

                If keyChangesStartIndex > -1 AndAlso detailedChangesStartIndex > keyChangesStartIndex Then
                    ' Capture text between "## Key Changes" and "### Detailed Changes"
                    logEntry.HighLevelSummary = logContent.Substring(keyChangesStartIndex, detailedChangesStartIndex - keyChangesStartIndex).Trim()
                End If

                ' C. Extract Detailed Changes (FullDetails)
                If detailedChangesStartIndex > -1 Then
                    Dim contentStartIndex As Integer = detailedChangesStartIndex + detailedChangesStartTag.Length

                    If contentStartIndex < logContent.Length Then
                        logEntry.FullDetails = logContent.Substring(contentStartIndex).TrimStart()
                    Else
                        logEntry.FullDetails = String.Empty
                    End If
                End If


                ' Only add valid entries
                If logEntry.VersionFileName <> String.Empty Then
                    logEntry.FileTime = File.GetLastWriteTime(logFilePath)
                    logEntries.Add(logEntry)
                End If

            Catch ex As Exception
                ' Skip this file and continue processing others if one fails.
            End Try
        Next

        ' 3. Sort and Mark Current (The newest entry based on its Time Stamp is the 'Current' one)
        logEntries = logEntries.OrderByDescending(Function(e) e.FileTime).ToList()

        If logEntries.Count > 0 Then
            logEntries.First().IsCurrent = True
        End If

        Return logEntries
    End Function


    Public Class RoundedPanel
        Inherits Panel

        Public Property CornerRadius As Integer = 15
        Public Property BorderColor As Color = Color.Black ' New property for border color
        Public Property BorderThickness As Integer = 4 ' New property for border thickness
        Protected Overrides Sub OnPaint(e As PaintEventArgs)
            MyBase.OnPaint(e)

            Dim g As Graphics = e.Graphics
            g.SmoothingMode = SmoothingMode.AntiAlias

            ' Create rounded rectangle path
            Using path As GraphicsPath = GetRoundedRectPath(Me.ClientRectangle, CornerRadius)
                Me.Region = New Region(path)

                ' Fill background
                Using brush As New SolidBrush(Me.BackColor)
                    g.FillPath(brush, path)
                End Using
                If BorderThickness > 0 Then
                    Using pen As New Pen(BorderColor, BorderThickness)
                        g.DrawPath(pen, path)
                    End Using
                End If
            End Using
            Me.Region = New Region(GetRoundedRectPath(Me.ClientRectangle, CornerRadius))

        End Sub

        Private Function GetRoundedRectPath(rect As Rectangle, radius As Integer) As GraphicsPath
            Dim path As New GraphicsPath()
            Dim diameter As Integer = radius * 2

            ' Adjust rectangle to account for border
            rect = New Rectangle(rect.X, rect.Y, rect.Width - 1, rect.Height - 1)

            ' Add arcs for each corner
            path.AddArc(rect.X, rect.Y, diameter, diameter, 180, 90)
            path.AddArc(rect.Right - diameter, rect.Y, diameter, diameter, 270, 90)
            path.AddArc(rect.Right - diameter, rect.Bottom - diameter, diameter, diameter, 0, 90)
            path.AddArc(rect.X, rect.Bottom - diameter, diameter, diameter, 90, 90)
            path.CloseFigure()

            Return path
        End Function
    End Class

    ' ==================== ROUNDED BUTTON CLASS ====================
    Public Class RoundedButton
        Inherits Button

        Public Property CornerRadius As Integer = 8
        Public Property HoverBackColor As Color = Color.LightGray
        Private isHovering As Boolean = False

        Public Sub New()
            Me.FlatStyle = FlatStyle.Flat
            Me.FlatAppearance.BorderSize = 0
        End Sub

        Protected Overrides Sub OnMouseEnter(e As EventArgs)
            MyBase.OnMouseEnter(e)
            isHovering = True
            Me.Invalidate()
        End Sub

        Protected Overrides Sub OnMouseLeave(e As EventArgs)
            MyBase.OnMouseLeave(e)
            isHovering = False
            Me.Invalidate()
        End Sub

        Protected Overrides Sub OnPaint(pevent As PaintEventArgs)
            MyBase.OnPaint(pevent)

            Dim g As Graphics = pevent.Graphics
            g.SmoothingMode = SmoothingMode.AntiAlias

            Using path As GraphicsPath = GetRoundedRectPath(Me.ClientRectangle, CornerRadius)
                Me.Region = New Region(path)

                ' Choose color based on hover state
                Dim bgColor As Color = If(isHovering, HoverBackColor, Me.BackColor)

                Using brush As New SolidBrush(bgColor)
                    g.FillPath(brush, path)
                End Using

                ' Draw text
                Using format As New StringFormat()
                    format.Alignment = StringAlignment.Center
                    format.LineAlignment = StringAlignment.Center

                    Using textBrush As New SolidBrush(Me.ForeColor)
                        g.DrawString(Me.Text, Me.Font, textBrush, Me.ClientRectangle, format)
                    End Using
                End Using
            End Using
        End Sub

        Private Function GetRoundedRectPath(rect As Rectangle, radius As Integer) As GraphicsPath
            Dim path As New GraphicsPath()
            Dim diameter As Integer = radius * 2

            rect = New Rectangle(rect.X, rect.Y, rect.Width - 1, rect.Height - 1)

            path.AddArc(rect.X, rect.Y, diameter, diameter, 180, 90)
            path.AddArc(rect.Right - diameter, rect.Y, diameter, diameter, 270, 90)
            path.AddArc(rect.Right - diameter, rect.Bottom - diameter, diameter, diameter, 0, 90)
            path.AddArc(rect.X, rect.Bottom - diameter, diameter, diameter, 90, 90)
            path.CloseFigure()

            Return path
        End Function
    End Class


    ' Constants for layout
    Private Const CARD_WIDTH As Integer = 450
    Private Const CARD_HEIGHT As Integer = 180
    Private Const CARD_SPACING As Integer = 40
    Private Const TIMELINE_LEFT_OFFSET As Integer = 50
    Private Const NODE_SIZE As Integer = 12

    Public Sub LoadTimeline(ByVal logEntries As List(Of LogEntry))
        ' Clear previous controls before drawing
        pnlTimelineContainer.Controls.Clear()

        If logEntries.Count = 0 Then
            ' Handle case with no entries
            Dim lbl As New Label()
            lbl.Text = "No log entries found."
            lbl.Location = New Point(10, 10)
            pnlTimelineContainer.Controls.Add(lbl)
            Return
        End If

        Dim currentY As Integer = 20 ' Starting vertical position

        ' 1. Draw the continuous vertical line
        Dim totalHeight As Integer = (logEntries.Count * (CARD_HEIGHT + CARD_SPACING)) - CARD_SPACING
        If totalHeight > 0 Then
            Dim linePanel As New Panel()
            linePanel.BackColor = Color.LightGray
            linePanel.Width = 2
            linePanel.Height = totalHeight
            linePanel.Location = New Point(TIMELINE_LEFT_OFFSET + (NODE_SIZE \ 2) - 1, 20 + (NODE_SIZE \ 2))
            pnlTimelineContainer.Controls.Add(linePanel)
            linePanel.SendToBack() ' Ensure the line is behind the nodes and cards
        End If

        ' 2. Iterate and draw each log entry (Node, Date Marker, Card)
        For Each entry As LogEntry In logEntries
            Dim cardColor As Color = Color.Gainsboro ' Use Gainsboro (light gray) for ALL cards
            Dim textColor As Color = Color.Black     ' Use Black text for ALL cards

            ' --- B. Draw the Node (Square) ---
            Dim NODE_SIZE_LARGE As Integer = 20
            Dim LINE_THICKNESS As Integer = 2 ' ASSUMPTION: The thickness of the vertical line in pixels.
            Dim PurpleColor As Color = Color.FromArgb(128, 0, 128)

            Dim pnlNode As New Panel()
            pnlNode.BackColor = PurpleColor
            pnlNode.Size = New Size(NODE_SIZE_LARGE, NODE_SIZE_LARGE)

            ' CALCULATE NEW CENTERED X POSITION
            ' 1. Find the center point of the vertical line:
            'Dim LineCenterOffset As Integer = TIMELINE_LEFT_OFFSET + (LINE_THICKNESS \ 2)
            Dim LineCenterOffset As Integer = TIMELINE_LEFT_OFFSET

            ' 2. Center the square (NODE) on that Line Center point:
            Dim CenteredX As Integer = LineCenterOffset - (NODE_SIZE_LARGE \ 2)

            ' Y-Centering remains correct:
            Dim CenteredY As Integer = currentY + (CARD_HEIGHT \ 2) - (NODE_SIZE_LARGE \ 2)

            pnlNode.Location = New Point(CenteredX, CenteredY)

            pnlTimelineContainer.Controls.Add(pnlNode)

            ' --- C. Draw the Version Card (Right Side) ---
            Dim pnlCard As New RoundedPanel()
            pnlCard.Size = New Size(CARD_WIDTH, CARD_HEIGHT)
            pnlCard.Location = New Point(TIMELINE_LEFT_OFFSET + 30, currentY)
            pnlCard.BackColor = cardColor
            pnlCard.BorderStyle = BorderStyle.FixedSingle ' For visibility
            pnlTimelineContainer.Controls.Add(pnlCard)

            ' 1. Version ID Label (e.g., E2K file name)
            Dim lblVersionID As New Label()
            lblVersionID.Text = Path.GetFileName(entry.VersionFileName) ' Just the filename
            lblVersionID.Font = New Font(lblVersionID.Font.FontFamily, 12, FontStyle.Bold)
            lblVersionID.ForeColor = textColor
            lblVersionID.Location = New Point(10, 10)
            lblVersionID.AutoSize = True
            pnlCard.Controls.Add(lblVersionID)

            ' 2. CURRENT Badge (if needed)
            If entry.IsCurrent Then
                Dim lblCurrent As New Label()
                lblCurrent.Text = "CURRENT"
                lblCurrent.BackColor = Color.Red ' Or a distinctive color
                lblCurrent.ForeColor = Color.White
                lblCurrent.Padding = New Padding(4, 2, 4, 2)
                lblCurrent.AutoSize = True
                lblCurrent.Location = New Point(pnlCard.Width - lblCurrent.Width - 15, 12)
                pnlCard.Controls.Add(lblCurrent)
            End If

            ' 3. Build Date
            Dim lblBuildDate As New Label()
            'lblBuildDate.Text = $"Built: {entry.LogTime.ToString("MMM dd, yyyy HH:mm")}"
            lblBuildDate.Text = $"Built: {entry.FileTime.ToString("MMM dd, yyyy HH:mm")}"
            lblBuildDate.ForeColor = textColor
            lblBuildDate.Location = New Point(10, 35)
            lblBuildDate.AutoSize = True
            pnlCard.Controls.Add(lblBuildDate)

            ' 4. Summary (Shortened to fit the button)


            Dim txtSummary As New TextBox() ' CHANGED to TextBox
            txtSummary.Text = "Summary:" & Environment.NewLine & entry.HighLevelSummary
            txtSummary.ForeColor = textColor
            txtSummary.Location = New Point(10, 60)
            txtSummary.Width = CARD_WIDTH - 20
            txtSummary.Height = 85 ' Define a fixed height for the summary area
            txtSummary.ReadOnly = True ' Prevent user from editing the log text
            txtSummary.Multiline = True ' Essential for wrapping text
            txtSummary.ScrollBars = ScrollBars.Vertical ' Essential for scrolling

            ' --- Card Summary Color Fix ---
            ' Set colors for ALL cards (current and history) to the same appearance.

            ' Set colors for the summary textbox (txtSummary)
            txtSummary.BackColor = Color.White ' Standard background color for all cards
            txtSummary.ForeColor = Color.Black ' Standard text color for all cards

            pnlCard.Controls.Add(txtSummary)
            txtSummary.SelectionStart = 0  ' Move the cursor to the beginning
            txtSummary.SelectionLength = 0 ' Deselect any text

            ' 5. **View Detailed Changes Button**
            Dim btnViewDetails As New Button()
            btnViewDetails.Text = "View Details"
            btnViewDetails.Tag = entry.FullDetails ' Store the detailed text in the button's Tag property
            btnViewDetails.Location = New Point(CARD_WIDTH - 110, pnlCard.Height - 30) ' Position at bottom right of card
            btnViewDetails.Cursor = Cursors.Hand

            ' Attach the event handler
            AddHandler btnViewDetails.Click, AddressOf BtnViewDetails_Click

            pnlCard.Controls.Add(btnViewDetails)

            currentY += CARD_HEIGHT + CARD_SPACING
        Next

        ' Set the minimum size for the container based on total height
        'pnlTimelineContainer.Height = currentY
        pnlTimelineContainer.Invalidate() ' Force redraw
    End Sub

    Private Sub BtnViewDetails_Click(sender As Object, e As EventArgs)
        Dim btn As Button = TryCast(sender, Button)

        If Not IsNothing(btn) Then
            Dim detailedText As String = CStr(btn.Tag)

            If Not String.IsNullOrEmpty(detailedText) Then
                ' Option 1: Use a simple message box (best for short detailed logs)
                ' MessageBox.Show(detailedText, "Detailed Changes", MessageBoxButtons.OK, MessageBoxIcon.Information)

                ' Option 2: Use a dedicated, scrollable form for long logs
                Dim detailForm As New Form()
                detailForm.Text = "Detailed Changes Log"
                detailForm.Size = New Size(600, 450)

                Dim txtDetails As New RichTextBox()
                txtDetails.Text = detailedText
                txtDetails.Dock = DockStyle.Fill
                txtDetails.ReadOnly = True

                detailForm.Controls.Add(txtDetails)
                detailForm.ShowDialog(Me) ' Show modally over the main viewer form

            Else
                MessageBox.Show("No detailed log information available for this version.", "Details Missing", MessageBoxButtons.OK, MessageBoxIcon.Warning)
            End If
        End If
    End Sub

    Private Function ExtractDateTimeFromE2K(ByVal e2kFilePath As String) As DateTime
        Dim logDateTime As DateTime = DateTime.MinValue ' Default value if parsing fails

        Try
            If File.Exists(e2kFilePath) Then
                ' Read only the first line of the E2K file
                Using reader As New StreamReader(e2kFilePath)
                    Dim firstLine As String = reader.ReadLine()

                    If Not String.IsNullOrEmpty(firstLine) Then
                        ' Search for the word "saved"
                        Dim savedIndex As Integer = firstLine.IndexOf("saved", StringComparison.OrdinalIgnoreCase)

                        If savedIndex > -1 Then
                            ' The date/time starts after "saved " (6 characters after 's')
                            Dim dateStringStart As Integer = savedIndex + 6

                            If dateStringStart < firstLine.Length Then
                                Dim dateString As String = firstLine.Substring(dateStringStart).Trim()

                                ' Attempt to parse the date string (e.g., "11/15/2025 3:50:59 PM")
                                DateTime.TryParse(dateString, logDateTime)
                            End If
                        End If
                    End If
                End Using
            End If

        Catch ex As Exception
            ' Log error that E2K reading failed, but return default DateTime.MinValue
        End Try

        Return logDateTime
    End Function
End Class