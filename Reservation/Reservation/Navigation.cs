using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Data.SqlClient;
using System.Drawing;
using System.Drawing.Printing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Reservation
{
    public partial class Navigation : Form
    {


        private float _initialFormWidth;
        private float _initialFormHeight;
        private ControlInfo[] _controlsInfo;



        private string _username;
        public Navigation(string username)
        {
            InitializeComponent();


            _username = username;


            _initialFormWidth = this.Width;
            _initialFormHeight = this.Height;

            // Store initial size and location of all controls
            _controlsInfo = new ControlInfo[this.Controls.Count];
            for (int i = 0; i < this.Controls.Count; i++)
            {
                Control c = this.Controls[i];
                _controlsInfo[i] = new ControlInfo(c.Left, c.Top, c.Width, c.Height, c.Font.Size);
            }

            // Set event handler for form resize
            this.Resize += Home_Resize;


        }


        private void Home_Resize(object sender, EventArgs e)
        {
            float widthRatio = this.Width / _initialFormWidth;
            float heightRatio = this.Height / _initialFormHeight;
            ResizeControls(this.Controls, widthRatio, heightRatio);
        }

        private void ResizeControls(Control.ControlCollection controls, float widthRatio, float heightRatio)
        {
            for (int i = 0; i < controls.Count; i++)
            {
                Control control = controls[i];
                ControlInfo controlInfo = _controlsInfo[i];

                control.Left = (int)(controlInfo.Left * widthRatio);
                control.Top = (int)(controlInfo.Top * heightRatio);
                control.Width = (int)(controlInfo.Width * widthRatio);
                control.Height = (int)(controlInfo.Height * heightRatio);

                // Adjust font size
                control.Font = new Font(control.Font.FontFamily, controlInfo.FontSize * Math.Min(widthRatio, heightRatio));
            }
        }

        private class ControlInfo
        {
            public int Left { get; set; }
            public int Top { get; set; }
            public int Width { get; set; }
            public int Height { get; set; }
            public float FontSize { get; set; }

            public ControlInfo(int left, int top, int width, int height, float fontSize)
            {
                Left = left;
                Top = top;
                Width = width;
                Height = height;
                FontSize = fontSize;
            }
        }

        private void dashboard_btn_Click(object sender, EventArgs e)
        {

        }

        private void dashboard_btn_Click_1(object sender, EventArgs e)
        {
            Home home = new Home(_username);
            this.Hide();    
            home.ShowDialog();
            this.Close();   
        }




        private void NavigateToForm(int requiredRole, Form targetForm, string unauthorizedMessage = "غير مسموح بالضغط على هذا الزرار")
        {
            if (GlobalUser.Role != requiredRole)
            {
                this.Hide();
                targetForm.ShowDialog();
                this.Close();
            }
            else
            {
                MessageBox.Show(unauthorizedMessage, "Unauthorized", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }


        private void button1_Click(object sender, EventArgs e)
        {
            NavigateToForm(3, new EditCustomerData(_username));
          

        }

        private void button2_Click(object sender, EventArgs e)
        {
            NavigateToForm(3, new UserLog(_username));
           
        }




        private void Navigation_Load(object sender, EventArgs e)
        {
            cashiernamelabel.Text= _username;
            if (GlobalUser.Role == 1)
            {
                button3.Visible = true;
                button4.Visible = true;
                button5.Visible = true;

            }
        }

        private void button3_Click(object sender, EventArgs e)
        {
            SignUp sign = new SignUp(_username);
            this.Hide();
            sign.ShowDialog();
            this.Close();
        }

        private void button5_Click(object sender, EventArgs e)
        {
            MenuItemsForm sign = new MenuItemsForm(_username);
            this.Hide();
            sign.ShowDialog();
            this.Close();
        }
    }
}


