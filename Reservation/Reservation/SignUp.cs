using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Data.SqlClient;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Reservation
{
    public partial class SignUp : Form
    {
        private string _username;
        public SignUp(string username)
        {
            _username = username;
            InitializeComponent();
        }

        private void signupbtn_Click(object sender, EventArgs e)
        {
            // Check if any of the required fields are empty
            if (string.IsNullOrWhiteSpace(usertxt.Text) || string.IsNullOrWhiteSpace(passwordtxt.Text) || string.IsNullOrWhiteSpace(confirmpasstxt.Text) || rolecombo.SelectedItem == null || string.IsNullOrWhiteSpace(fullnametxt.Text))
            {
                MessageBox.Show("Please fill in all fields.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // Check if the password and confirm password fields match
            if (passwordtxt.Text != confirmpasstxt.Text)
            {
                MessageBox.Show("Passwords do not match.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // Map role names to role IDs
            Dictionary<string, int> roleMapping = new Dictionary<string, int>
    {
        { "Super", 1 },
        { "admin", 2 },
        { "Cashier", 3 },
        { "Control", 4 },
                {"SuperCashier",5 }

    };

            // Get the selected role name
            string selectedRole = rolecombo.SelectedItem.ToString();

            // Validate the selected role and get its corresponding ID
            if (!roleMapping.TryGetValue(selectedRole, out int role))
            {
                MessageBox.Show("Invalid role selected.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // Replace with your actual connection string
            using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    connection.Open();

                    // Check if the username already exists
                    string checkUserQuery = "SELECT COUNT(*) FROM Cashier WHERE Username = @Username";
                    using (SqlCommand checkUserCommand = new SqlCommand(checkUserQuery, connection))
                    {
                        checkUserCommand.Parameters.AddWithValue("@Username", usertxt.Text);
                        int userCount = (int)checkUserCommand.ExecuteScalar();

                        if (userCount > 0)
                        {
                            MessageBox.Show("Username already exists. Please choose a different username.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                            return;
                        }
                    }

                    // Insert the new user into the database
                    string query = "INSERT INTO Cashier (Username, Password, role , fullname) VALUES (@Username, @Password, @role , @fullname)";
                    using (SqlCommand command = new SqlCommand(query, connection))
                    {
                        string password = passwordtxt.Text; // Consider hashing the password here
                        command.Parameters.AddWithValue("@Username", usertxt.Text);
                        command.Parameters.AddWithValue("@Password", password);
                        command.Parameters.AddWithValue("@role", role);
                        command.Parameters.AddWithValue("@fullname", fullnametxt.Text);// Use the role from the dictionary

                        int result = command.ExecuteNonQuery();

                        if (result > 0)
                        {
                            MessageBox.Show("Sign up successful!", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
                            usertxt.Text = null;
                            passwordtxt.Text = null;
                            confirmpasstxt.Text = null;
                            rolecombo.SelectedIndex = -1; // Clear the role combo box selection
                            fullnametxt.Text = null;    
                        }
                        else
                        {
                            MessageBox.Show("Sign up failed. Please try again.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        }
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show("An error occurred: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }

        private void SignUp_Load(object sender, EventArgs e)
        {

        }

        private void homebackbtn_LinkClicked(object sender, LinkLabelLinkClickedEventArgs e)
        {
            Navigation navigation = new Navigation(_username);
            this.Hide();
            navigation.ShowDialog();
            this.Close();
        }
    }
}
