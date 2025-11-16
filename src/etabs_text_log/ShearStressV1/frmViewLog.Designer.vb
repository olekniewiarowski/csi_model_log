<Global.Microsoft.VisualBasic.CompilerServices.DesignerGenerated()>
Partial Class frmViewLog
    Inherits System.Windows.Forms.Form

    'Form overrides dispose to clean up the component list.
    <System.Diagnostics.DebuggerNonUserCode()>
    Protected Overrides Sub Dispose(ByVal disposing As Boolean)
        Try
            If disposing AndAlso components IsNot Nothing Then
                components.Dispose()
            End If
        Finally
            MyBase.Dispose(disposing)
        End Try
    End Sub

    'Required by the Windows Form Designer
    Private components As System.ComponentModel.IContainer

    'NOTE: The following procedure is required by the Windows Form Designer
    'It can be modified using the Windows Form Designer.  
    'Do not modify it using the code editor.
    <System.Diagnostics.DebuggerStepThrough()>
    Private Sub InitializeComponent()
        Me.pnlTimelineContainer = New System.Windows.Forms.Panel()
        Me.SuspendLayout()
        '
        'pnlTimelineContainer
        '
        Me.pnlTimelineContainer.AutoScroll = True
        Me.pnlTimelineContainer.Location = New System.Drawing.Point(23, 12)
        Me.pnlTimelineContainer.Name = "pnlTimelineContainer"
        Me.pnlTimelineContainer.Size = New System.Drawing.Size(1634, 1222)
        Me.pnlTimelineContainer.TabIndex = 1
        '
        'frmViewLog
        '
        Me.AutoScaleDimensions = New System.Drawing.SizeF(16.0!, 31.0!)
        Me.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font
        Me.ClientSize = New System.Drawing.Size(1748, 1246)
        Me.Controls.Add(Me.pnlTimelineContainer)
        Me.Name = "frmViewLog"
        Me.Text = "frmViewLog"
        Me.ResumeLayout(False)

    End Sub
    Friend WithEvents pnlTimelineContainer As Windows.Forms.Panel
End Class
