using System;
using System.Data.SqlClient;
using System.Drawing;
using System.Windows.Forms;

namespace Reservation
{
    public partial class Login : Form
    {

        private float _initialFormWidth;
        private float _initialFormHeight;
        private ControlInfo[] _controlsInfo;


        public Login()
        {
            InitializeComponent();

            // Attach KeyDown events for handling Enter key navigation
            usernametxt.KeyDown += new KeyEventHandler(usernametxt_KeyDown);
            passwordtxt.KeyDown += new KeyEventHandler(passwordtxt_KeyDown);



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
        private void exit_Click(object sender, EventArgs e)
        {
            Application.Exit(); // Exit the application
        }

        private void login_showPass_CheckedChanged(object sender, EventArgs e)
        {
            // Toggle password visibility
            passwordtxt.PasswordChar = login_showPass.Checked ? '\0' : '*';
        }

        private void login_btn_Click(object sender, EventArgs e)
        {
            string username = usernametxt.Text.Trim();
            string password = passwordtxt.Text.Trim();

            if (string.IsNullOrEmpty(username) || string.IsNullOrEmpty(password))
            {
                MessageBox.Show("Please enter both username and password.", "Invalid Input", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            try
            {
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    connection.Open();

                    // SQL query to validate login and retrieve user info
                    string query = "SELECT FullName, Role FROM Cashier WHERE Username = @Username AND Password = @Password";

                    using (SqlCommand command = new SqlCommand(query, connection))
                    {
                        // Add parameters to prevent SQL injection
                        command.Parameters.AddWithValue("@Username", username);
                        command.Parameters.AddWithValue("@Password", password);

                        using (SqlDataReader reader = command.ExecuteReader())
                        {
                            if (reader.Read()) // If a matching record is found
                            {
                                // Set global user information
                                GlobalUser.FullName = reader["FullName"].ToString();
                                GlobalUser.Role = Convert.ToInt32(reader["Role"]);

                                // Navigate based on the role
                                NavigateToRoleForm();
                            }
                            else
                            {
                                // If no matching user is found
                                MessageBox.Show("Invalid username or password. Please try again.", "Login Failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"An error occurred while validating login: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void NavigateToRoleForm()
        {
            // Navigate based on the user's role
            switch (GlobalUser.Role)
            {
                case 1: // Role 1: Navigation
                    Navigation navigationForm = new Navigation(GlobalUser.FullName);
                    this.Hide();
                    navigationForm.ShowDialog();
                    this.Close();
                    break;

                case 2: // Role 2: Home
                    Navigation homeForm = new Navigation(GlobalUser.FullName);
                    this.Hide();
                    homeForm.ShowDialog();
                    this.Close();
                    break;

                case 3: // Role 3: Navigation
                    Home navigationForm3 = new Home(GlobalUser.FullName);
                    this.Hide();
                    navigationForm3.ShowDialog();
                    this.Close();
                    break;

                case 4: // Role 4: ReservationsReport
                    ReservationsReport reservationsReportForm = new ReservationsReport(GlobalUser.FullName);
                    this.Hide();
                    reservationsReportForm.ShowDialog();
                    this.Close();
                    break;
                case 5: // Role 2: Home
                    Home homy = new Home(GlobalUser.FullName);
                    this.Hide();
                    homy.ShowDialog();
                    this.Close();
                    break;

                default: // Unknown role
                    MessageBox.Show("Your role is not recognized. Please contact the administrator.", "Access Denied", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    break;
            }
        }

        private void usernametxt_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Enter) // Check if the Enter key is pressed
            {
                passwordtxt.Focus(); // Move focus to the password textbox
            }
        }

        private void passwordtxt_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Enter) // Check if the Enter key is pressed
            {
                login_btn_Click(sender, e); // Trigger login logic
            }
        }

        private void Login_Load(object sender, EventArgs e)
        {

        }
    }
}
