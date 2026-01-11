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
    public partial class EditPayments : Form
    {
        private float _initialFormWidth;
        private float _initialFormHeight;
        private ControlInfo[] _controlsInfo;

        private string _username;
        public EditPayments(string username)
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



        private void ManageReservationGridview_CellValueChanged(object sender, DataGridViewCellEventArgs e)
        {
            if (e.RowIndex >= 0)
            {

                editedRows.Add(e.RowIndex);

            }
        }

                private void Editorder_Load(object sender, EventArgs e)
        {
            // Load reservation data when the form loads
            LoadReservations();
        }

        private void LoadReservations()
        {
            // Query the Payments table
            string paymentsQuery = @"
SELECT TOP 200 
    p.PaymentID, 
    c.Name AS CustomerName, 
    p.ReservationID, 
    p.TotalAmount, 
    p.PaidAmount, 
    p.RemainingAmount 
FROM Payments p
INNER JOIN Customer c ON p.CustomerID = c.CustomerID
ORDER BY p.PaymentID DESC"; // Order by PaymentID in descending order


            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    // Fetch payments data
                    SqlDataAdapter paymentsAdapter = new SqlDataAdapter(paymentsQuery, conn);
                    DataTable paymentsTable = new DataTable();
                    paymentsAdapter.Fill(paymentsTable);

                    // Bind payments data to the DataGridView
                    ManageReservationGridview.DataSource = paymentsTable;

                    // Auto-size columns to fit the content
                    ManageReservationGridview.AutoResizeColumns(DataGridViewAutoSizeColumnsMode.AllCells);

                    // Stretch columns to fill the grid's width
                    ManageReservationGridview.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;

                    // Adjust column widths for PaymentID and CustomerID to take up smaller space
                    ManageReservationGridview.Columns["PaymentID"].AutoSizeMode = DataGridViewAutoSizeColumnMode.AllCells;
                    ManageReservationGridview.Columns["PaymentID"].Width = 80;

                    ManageReservationGridview.Columns["CustomerName"].AutoSizeMode = DataGridViewAutoSizeColumnMode.AllCells;
                    ManageReservationGridview.Columns["CustomerName"].Width = 80;

                    // Make only PaidAmount column editable
                    foreach (DataGridViewColumn column in ManageReservationGridview.Columns)
                    {
                        if (column.Name == "PaidAmount")
                        {
                            column.ReadOnly = false; // Allow editing PaidAmount
                        }
                        else
                        {
                            column.ReadOnly = true; // Other columns remain read-only
                        }
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error loading payments: {ex.Message}");
                }
            }
        }

        // This method will handle the Load button click
        private void loadbtn_Click(object sender, EventArgs e)
        {
            LoadReservations();
        }
        private List<int> editedRows = new List<int>();
        // Method to update PaidAmount in the Payments table
        private void updatebtn_Click(object sender, EventArgs e)
        {
            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                if (editedRows.Count == 0)
                {
                    MessageBox.Show("No changes to update.");
                    return;
                }
                try
                {
                    conn.Open();

                    foreach (int rowIndex in editedRows)
                    {
                        DataGridViewRow row = ManageReservationGridview.Rows[rowIndex];

                        // Get updated PaidAmount and PaymentID
                        if (row.Cells["PaidAmount"].Value != DBNull.Value && row.Cells["PaymentID"].Value != DBNull.Value)
                        {
                            decimal paidAmount = Convert.ToDecimal(row.Cells["PaidAmount"].Value);
                            int paymentID = Convert.ToInt32(row.Cells["PaymentID"].Value);

                            // Update query for the Payments table
                            string query = "UPDATE Payments SET PaidAmount = @PaidAmount WHERE PaymentID = @PaymentID";

                            using (SqlCommand cmd = new SqlCommand(query, conn))
                            {
                                cmd.Parameters.AddWithValue("@PaidAmount", paidAmount);
                                cmd.Parameters.AddWithValue("@PaymentID", paymentID);

                                cmd.ExecuteNonQuery();
                            }

                            // Log the update in the UserLog table
                            string action = $"Edited PaymentID: {paymentID}, PaidAmount: {paidAmount} , EditPayment";
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
                    MessageBox.Show("Paid amounts updated successfully!", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
                   
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

       

        private void button1_Click(object sender, EventArgs e)
        {
            EditCustomerData editCustomerData = new EditCustomerData(_username);
            this.Hide();
            editCustomerData.ShowDialog();
            this.Close();
        }

        private void button3_Click(object sender, EventArgs e)
        {
            EditReservation editReservation = new EditReservation(_username);
            this.Hide();
            editReservation.ShowDialog();
            this.Close();
        }

        private void EditPayments_Load(object sender, EventArgs e)
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

      
        private void label3_Click(object sender, EventArgs e)
        {

        }
    }
}
