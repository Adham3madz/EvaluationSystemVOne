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
    public partial class EditCustomerData : Form
    {
        private float _initialFormWidth;
        private float _initialFormHeight;
        private ControlInfo[] _controlsInfo;


        private string _username;
        public EditCustomerData(string username)
        {
            InitializeComponent();
            _username = username;



            ManageReservationGridview.CellValueChanged += ManageReservationGridview_CellValueChanged;

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

        private void Editorder_Load(object sender, EventArgs e)
        {
            // Load reservation data when the form loads
            LoadReservations();
        }

        private void LoadReservations()
        {
            string customersQuery = "SELECT TOP 1000 CustomerID, Name, PhoneNumber FROM Customer  ORDER BY CustomerID DESC"; // Adjusted to query the Customers table

            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    // Fetch customer data
                    SqlDataAdapter customersAdapter = new SqlDataAdapter(customersQuery, conn);
                    DataTable customersTable = new DataTable();
                    customersAdapter.Fill(customersTable);

                    // Bind customer data to the DataGridView
                    ManageReservationGridview.DataSource = customersTable;

                    // Auto-size columns to fit the content
                    ManageReservationGridview.AutoResizeColumns(DataGridViewAutoSizeColumnsMode.AllCells);

                    // Alternatively, stretch columns to fill the grid's width
                    ManageReservationGridview.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;

                    // Adjust CustomerID column to take up smaller space
                    ManageReservationGridview.Columns["CustomerID"].AutoSizeMode = DataGridViewAutoSizeColumnMode.AllCells;
                    ManageReservationGridview.Columns["CustomerID"].Width = 80; // Set a fixed width for CustomerID column

                    // Optionally, you can hide specific columns from the view if necessary
                    // Example: Hide CustomerID column (if you don't want it visible)
                    // ManageReservationGridview.Columns["CustomerID"].Visible = false;
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error loading customers: {ex.Message}");
                }
            }
        }




        // This method will handle the search button click
        private void loadbtn_Click(object sender, EventArgs e)
        {



            LoadReservations();
        }




        private HashSet<int> editedRows = new HashSet<int>();


        private void ManageReservationGridview_CellValueChanged(object sender, DataGridViewCellEventArgs e)
        {
            if (e.RowIndex >= 0)
            {

                editedRows.Add(e.RowIndex);

            }
        }

                // Method to update PaidAmount in both Payments and DailyPayments tables


                private void updatebtn_Click(object sender, EventArgs e)
        {

            if (editedRows.Count == 0)
            {
                MessageBox.Show("No changes to update.");
                return;
            }
            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    conn.Open();

                    foreach (int rowIndex in editedRows)
                    {
                        DataGridViewRow row = ManageReservationGridview.Rows[rowIndex];

                        // Check if Name or PhoneNumber was edited
                        string name = row.Cells["Name"].Value != DBNull.Value ? row.Cells["Name"].Value.ToString() : string.Empty;
                        string phoneNumber = row.Cells["PhoneNumber"].Value != DBNull.Value ? row.Cells["PhoneNumber"].Value.ToString() : string.Empty;
                        int customerID = row.Cells["CustomerID"].Value != DBNull.Value ? Convert.ToInt32(row.Cells["CustomerID"].Value) : 0;

                        if (!string.IsNullOrEmpty(name) || !string.IsNullOrEmpty(phoneNumber))
                        {
                            // Prepare the update query for the Customer table
                            string query = @"
                    UPDATE Customer
                    SET Name = @Name,
                        PhoneNumber = @PhoneNumber
                    WHERE CustomerID = @CustomerID";

                            using (SqlCommand cmd = new SqlCommand(query, conn))
                            {
                                cmd.Parameters.AddWithValue("@Name", name);
                                cmd.Parameters.AddWithValue("@PhoneNumber", phoneNumber);
                                cmd.Parameters.AddWithValue("@CustomerID", customerID);

                                // Execute the update query
                                cmd.ExecuteNonQuery();
                            }

                            // Log the action in the UserLog table
                            string action = $"Edited CustomerID: {customerID}, Name: {name}, PhoneNumber: {phoneNumber} , EditCustomerData";
                            string logQuery = "INSERT INTO UserLog (CashierName, Action) VALUES (@CashierName, @Action)";

                            using (SqlCommand logCmd = new SqlCommand(logQuery, conn))
                            {
                                logCmd.Parameters.AddWithValue("@CashierName", _username);
                                logCmd.Parameters.AddWithValue("@Action", action);

                                logCmd.ExecuteNonQuery();
                            }
                        }
                    }
                    editedRows.Clear();
                    MessageBox.Show("Customer records updated successfully!", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
                   
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error updating records: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }

        private void dashboard_btn_Click(object sender, EventArgs e)
        {
            Editorder editorder = new Editorder(_username);
            this.Hide();
            editorder.ShowDialog();
            this.Close();   
        }

        private void button2_Click(object sender, EventArgs e)
        {
            EditPayments editPayments = new EditPayments(_username); 
            this.Hide();
            editPayments.ShowDialog();
            this.Close();
            
        }

        private void button3_Click(object sender, EventArgs e)
        {
            EditReservation editReservation = new EditReservation(_username);
            this.Hide();
            editReservation.ShowDialog();
            this.Close();
        }

        private void panel1_Paint(object sender, PaintEventArgs e)
        {

        }

        private void EditCustomerData_Load(object sender, EventArgs e)
        {
            cashiernamelabel.Text = _username;
        }

        private void backkbtn_Click(object sender, EventArgs e)
        {
            Navigation navigation = new Navigation(_username);
            this.Hide();
            navigation.ShowDialog();
            this.Close();
        }

        private void label4_Click(object sender, EventArgs e)
        {
            Login login = new Login();
            this.Hide();
            login.ShowDialog();
            this.Close();
        }

        private void ApplyFilter()
        {
            if (ManageReservationGridview.DataSource is DataTable dataTable)
            {
                string filter = "";

                if (filterselectioncombo.SelectedIndex == 0)  // "اسم المبلغ" selected
                {
                    if (!string.IsNullOrWhiteSpace(filteringTxtBox.Text))
                    {
                        filter = $"Name LIKE '%{filteringTxtBox.Text}%'";
                    }
                }
                else if (filterselectioncombo.SelectedIndex == 1)  // "المكان" selected
                {
                    if (!string.IsNullOrWhiteSpace(filteringTxtBox.Text))
                    {
                        filter = $"PhoneNumber LIKE '%{filteringTxtBox.Text}%'";
                    }
                }



                // Apply the filter to the DataTable
                dataTable.DefaultView.RowFilter = filter;
            }


        }

        private void filterselectioncombo_SelectedIndexChanged(object sender, EventArgs e)
        {
            ApplyFilter();
        }

        private void filteringTxtBox_TextChanged_1(object sender, EventArgs e)
        {
            ApplyFilter();
        }

       
    }
}
