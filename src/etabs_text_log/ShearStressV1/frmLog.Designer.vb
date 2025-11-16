Imports System.Windows.Forms

<Global.Microsoft.VisualBasic.CompilerServices.DesignerGenerated()>
Partial Class frmLog
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
        Me.btnLog = New System.Windows.Forms.Button()
        Me.txtLog = New System.Windows.Forms.TextBox()
        Me.btnViewLog = New System.Windows.Forms.Button()
        Me.btnRunLLM = New System.Windows.Forms.Button()
        Me.btnSelectLogDirectory = New System.Windows.Forms.Button()
        Me.SuspendLayout()
        '
        'btnLog
        '
        Me.btnLog.Location = New System.Drawing.Point(12, 140)
        Me.btnLog.Name = "btnLog"
        Me.btnLog.Size = New System.Drawing.Size(227, 87)
        Me.btnLog.TabIndex = 0
        Me.btnLog.Text = "Create Log"
        Me.btnLog.UseVisualStyleBackColor = True
        '
        'txtLog
        '
        Me.txtLog.Location = New System.Drawing.Point(12, 419)
        Me.txtLog.Multiline = True
        Me.txtLog.Name = "txtLog"
        Me.txtLog.Size = New System.Drawing.Size(445, 81)
        Me.txtLog.TabIndex = 1
        '
        'btnViewLog
        '
        Me.btnViewLog.Location = New System.Drawing.Point(12, 326)
        Me.btnViewLog.Name = "btnViewLog"
        Me.btnViewLog.Size = New System.Drawing.Size(212, 87)
        Me.btnViewLog.TabIndex = 2
        Me.btnViewLog.Text = "View Log"
        Me.btnViewLog.UseVisualStyleBackColor = True
        '
        'btnRunLLM
        '
        Me.btnRunLLM.Location = New System.Drawing.Point(12, 233)
        Me.btnRunLLM.Name = "btnRunLLM"
        Me.btnRunLLM.Size = New System.Drawing.Size(223, 87)
        Me.btnRunLLM.TabIndex = 3
        Me.btnRunLLM.Text = "Compare Log"
        Me.btnRunLLM.UseVisualStyleBackColor = True
        '
        'btnSelectLogDirectory
        '
        Me.btnSelectLogDirectory.Location = New System.Drawing.Point(12, 30)
        Me.btnSelectLogDirectory.Name = "btnSelectLogDirectory"
        Me.btnSelectLogDirectory.Size = New System.Drawing.Size(199, 90)
        Me.btnSelectLogDirectory.TabIndex = 4
        Me.btnSelectLogDirectory.Text = "BROWSE"
        Me.btnSelectLogDirectory.UseVisualStyleBackColor = True
        '
        'frmLog
        '
        Me.AutoScaleDimensions = New System.Drawing.SizeF(16.0!, 31.0!)
        Me.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font
        Me.BackColor = System.Drawing.Color.White
        Me.ClientSize = New System.Drawing.Size(471, 512)
        Me.Controls.Add(Me.btnSelectLogDirectory)
        Me.Controls.Add(Me.btnRunLLM)
        Me.Controls.Add(Me.btnViewLog)
        Me.Controls.Add(Me.txtLog)
        Me.Controls.Add(Me.btnLog)
        Me.Margin = New System.Windows.Forms.Padding(8, 7, 8, 7)
        Me.MinimumSize = New System.Drawing.Size(400, 300)
        Me.Name = "frmLog"
        Me.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen
        Me.Text = "ETABS Plugin Main Menu"
        Me.ResumeLayout(False)
        Me.PerformLayout()

    End Sub

    Friend WithEvents btnLog As Button
    Friend WithEvents txtLog As TextBox
    Friend WithEvents btnViewLog As Button
    Friend WithEvents btnRunLLM As Button
    Friend WithEvents btnSelectLogDirectory As Button
End Class