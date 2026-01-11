namespace Reservation
{
    partial class SingleReservationEdit
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            this.panel1 = new System.Windows.Forms.Panel();
            this.label2 = new System.Windows.Forms.Label();
            this.label1 = new System.Windows.Forms.Label();
            this.filteringTxtBox = new System.Windows.Forms.TextBox();
            this.updatebtn = new System.Windows.Forms.Button();
            this.loadbtn = new System.Windows.Forms.Button();
            this.ManageReservationGridview = new System.Windows.Forms.DataGridView();
            this.deletebtn = new System.Windows.Forms.Button();
            this.backkbtn = new System.Windows.Forms.Button();
            this.panel1.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.ManageReservationGridview)).BeginInit();
            this.SuspendLayout();
            // 
            // panel1
            // 
            this.panel1.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(33)))), ((int)(((byte)(11)))), ((int)(((byte)(97)))));
            this.panel1.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.panel1.Controls.Add(this.label2);
            this.panel1.Dock = System.Windows.Forms.DockStyle.Top;
            this.panel1.Location = new System.Drawing.Point(0, 0);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(840, 35);
            this.panel1.TabIndex = 0;
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Font = new System.Drawing.Font("Tahoma", 9.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.label2.ForeColor = System.Drawing.Color.White;
            this.label2.Location = new System.Drawing.Point(7, 9);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(89, 16);
            this.label2.TabIndex = 1;
            this.label2.Text = "حجوزات رمضان";
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Font = new System.Drawing.Font("Stencil", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.label1.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(33)))), ((int)(((byte)(11)))), ((int)(((byte)(97)))));
            this.label1.Location = new System.Drawing.Point(499, 271);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(69, 22);
            this.label1.TabIndex = 51;
            this.label1.Text = "رقم الحجز";
            // 
            // filteringTxtBox
            // 
            this.filteringTxtBox.Location = new System.Drawing.Point(318, 273);
            this.filteringTxtBox.Name = "filteringTxtBox";
            this.filteringTxtBox.Size = new System.Drawing.Size(175, 20);
            this.filteringTxtBox.TabIndex = 53;
            this.filteringTxtBox.TextChanged += new System.EventHandler(this.filteringTxtBox_TextChanged);
            // 
            // updatebtn
            // 
            this.updatebtn.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(33)))), ((int)(((byte)(11)))), ((int)(((byte)(97)))));
            this.updatebtn.Cursor = System.Windows.Forms.Cursors.Hand;
            this.updatebtn.FlatAppearance.CheckedBackColor = System.Drawing.Color.FromArgb(((int)(((byte)(75)))), ((int)(((byte)(8)))), ((int)(((byte)(138)))));
            this.updatebtn.FlatAppearance.MouseDownBackColor = System.Drawing.Color.FromArgb(((int)(((byte)(75)))), ((int)(((byte)(8)))), ((int)(((byte)(138)))));
            this.updatebtn.FlatAppearance.MouseOverBackColor = System.Drawing.Color.FromArgb(((int)(((byte)(75)))), ((int)(((byte)(8)))), ((int)(((byte)(138)))));
            this.updatebtn.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.updatebtn.Font = new System.Drawing.Font("Arial Narrow", 15.75F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.updatebtn.ForeColor = System.Drawing.Color.White;
            this.updatebtn.Location = new System.Drawing.Point(79, 260);
            this.updatebtn.Name = "updatebtn";
            this.updatebtn.Size = new System.Drawing.Size(140, 40);
            this.updatebtn.TabIndex = 50;
            this.updatebtn.Text = "تعديل حجز";
            this.updatebtn.UseVisualStyleBackColor = false;
            this.updatebtn.Click += new System.EventHandler(this.updatebtn_Click);
            // 
            // loadbtn
            // 
            this.loadbtn.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(33)))), ((int)(((byte)(11)))), ((int)(((byte)(97)))));
            this.loadbtn.Cursor = System.Windows.Forms.Cursors.Hand;
            this.loadbtn.FlatAppearance.CheckedBackColor = System.Drawing.Color.FromArgb(((int)(((byte)(75)))), ((int)(((byte)(8)))), ((int)(((byte)(138)))));
            this.loadbtn.FlatAppearance.MouseDownBackColor = System.Drawing.Color.FromArgb(((int)(((byte)(75)))), ((int)(((byte)(8)))), ((int)(((byte)(138)))));
            this.loadbtn.FlatAppearance.MouseOverBackColor = System.Drawing.Color.FromArgb(((int)(((byte)(75)))), ((int)(((byte)(8)))), ((int)(((byte)(138)))));
            this.loadbtn.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.loadbtn.Font = new System.Drawing.Font("Arial Narrow", 15.75F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.loadbtn.ForeColor = System.Drawing.Color.White;
            this.loadbtn.Location = new System.Drawing.Point(618, 260);
            this.loadbtn.Name = "loadbtn";
            this.loadbtn.Size = new System.Drawing.Size(140, 40);
            this.loadbtn.TabIndex = 47;
            this.loadbtn.Text = "بحث طلب";
            this.loadbtn.UseVisualStyleBackColor = false;
            this.loadbtn.Click += new System.EventHandler(this.loadbtn_Click);
            // 
            // ManageReservationGridview
            // 
            this.ManageReservationGridview.AutoSizeColumnsMode = System.Windows.Forms.DataGridViewAutoSizeColumnsMode.Fill;
            this.ManageReservationGridview.AutoSizeRowsMode = System.Windows.Forms.DataGridViewAutoSizeRowsMode.AllCells;
            this.ManageReservationGridview.ColumnHeadersHeightSizeMode = System.Windows.Forms.DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            this.ManageReservationGridview.Location = new System.Drawing.Point(79, 40);
            this.ManageReservationGridview.Name = "ManageReservationGridview";
            this.ManageReservationGridview.Size = new System.Drawing.Size(679, 196);
            this.ManageReservationGridview.TabIndex = 49;
            this.ManageReservationGridview.CellClick += new System.Windows.Forms.DataGridViewCellEventHandler(this.ManageReservationGridview_CellClick);
            // 
            // deletebtn
            // 
            this.deletebtn.Location = new System.Drawing.Point(109, 306);
            this.deletebtn.Name = "deletebtn";
            this.deletebtn.Size = new System.Drawing.Size(75, 23);
            this.deletebtn.TabIndex = 54;
            this.deletebtn.Text = "مسح";
            this.deletebtn.UseVisualStyleBackColor = true;
            this.deletebtn.Visible = false;
            this.deletebtn.Click += new System.EventHandler(this.deletebtn_Click);
            // 
            // backkbtn
            // 
            this.backkbtn.BackgroundImage = global::Reservation.Properties.Resources.Back_Button_Download_Transparent_PNG_Image;
            this.backkbtn.BackgroundImageLayout = System.Windows.Forms.ImageLayout.Stretch;
            this.backkbtn.Location = new System.Drawing.Point(9, 41);
            this.backkbtn.Name = "backkbtn";
            this.backkbtn.Size = new System.Drawing.Size(52, 41);
            this.backkbtn.TabIndex = 48;
            this.backkbtn.UseVisualStyleBackColor = true;
            this.backkbtn.Click += new System.EventHandler(this.backkbtn_Click);
            // 
            // SingleReservationEdit
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(840, 337);
            this.Controls.Add(this.deletebtn);
            this.Controls.Add(this.backkbtn);
            this.Controls.Add(this.label1);
            this.Controls.Add(this.filteringTxtBox);
            this.Controls.Add(this.updatebtn);
            this.Controls.Add(this.loadbtn);
            this.Controls.Add(this.ManageReservationGridview);
            this.Controls.Add(this.panel1);
            this.ImeMode = System.Windows.Forms.ImeMode.On;
            this.Name = "SingleReservationEdit";
            this.ShowIcon = false;
            this.SizeGripStyle = System.Windows.Forms.SizeGripStyle.Show;
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "تعديل";
            this.WindowState = System.Windows.Forms.FormWindowState.Maximized;
            this.Load += new System.EventHandler(this.Editorder_Load_1);
            this.panel1.ResumeLayout(false);
            this.panel1.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.ManageReservationGridview)).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Panel panel1;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.Button backkbtn;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.TextBox filteringTxtBox;
        private System.Windows.Forms.Button updatebtn;
        private System.Windows.Forms.Button loadbtn;
        private System.Windows.Forms.DataGridView ManageReservationGridview;
        private System.Windows.Forms.Button deletebtn;
    }
}