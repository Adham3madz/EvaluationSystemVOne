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
    public partial class SingleOrderEdit : Form
    {
        private string _username;



        private float _initialFormWidth;
        private float _initialFormHeight;
        private ControlInfo[] _controlsInfo;

        public SingleOrderEdit(string username)
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
            // Get the filter value from the TextBox
            string filterValue = filteringTxtBox.Text.Trim();

            // If the TextBox is empty, do nothing
            if (string.IsNullOrEmpty(filterValue))
            {
                ManageReservationGridview.DataSource = null; // Clear the DataGridView
                return;
            }

            // Query to fetch reservations with filtering
            string reservationsQuery = "SELECT * FROM View_ManageReservationsDetails WHERE Reservationid = @ReservationId ORDER BY Reservationid DESC";
            string menuItemsQuery = "SELECT ItemName FROM Menu";

            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    // Fetch reservations data
                    SqlDataAdapter reservationsAdapter = new SqlDataAdapter(reservationsQuery, conn);
                    reservationsAdapter.SelectCommand.Parameters.AddWithValue("@ReservationId", filterValue);

                    DataTable reservationsTable = new DataTable();
                    reservationsAdapter.Fill(reservationsTable);

                    // Fetch menu items data
                    SqlDataAdapter menuItemsAdapter = new SqlDataAdapter(menuItemsQuery, conn);
                    DataTable menuItemsTable = new DataTable();
                    menuItemsAdapter.Fill(menuItemsTable);

                    // Bind reservations data to the DataGridView
                    ManageReservationGridview.DataSource = reservationsTable;

                    // Check if the MenuItemNameComboBox column already exists
                    if (ManageReservationGridview.Columns.Contains("MenuItemName"))
                    {
                        // Create a DataGridViewComboBoxColumn for MenuItemName
                        DataGridViewComboBoxColumn menuItemComboBox = new DataGridViewComboBoxColumn
                        {
                            HeaderText = "MenuItemName",
                            DataPropertyName = "MenuItemName", // Bind to MenuItemName column
                            DataSource = menuItemsTable,
                            DisplayMember = "ItemName", // Column to display in the combo box
                            ValueMember = "ItemName", // Column value to use for selection
                            Name = "MenuItemNameComboBox" // Unique column name
                        };

                        // Replace the existing MenuItemName column with the combo box column
                        int columnIndex = ManageReservationGridview.Columns["MenuItemName"].Index;
                        ManageReservationGridview.Columns.RemoveAt(columnIndex);
                        ManageReservationGridview.Columns.Insert(columnIndex, menuItemComboBox);
                    }
                    else
                    {
                        // If the column exists, update its DataSource
                        var comboBoxColumn = ManageReservationGridview.Columns["MenuItemName"] as DataGridViewComboBoxColumn;
                        if (comboBoxColumn != null)
                        {
                            comboBoxColumn.DataSource = menuItemsTable;
                        }
                    }

                    // Hide specific columns from the view
                    string[] columnsToHide = new string[]
                    {
                "CustomerID",
                "RestaurantID",
                "RestaurantName",
                "NumberOfGuests",
                "DateSubmitted",
                "OrderDetailID",
                "PaymentID",
                "TotalAmount",
                "PaidAmount",
                "RemainingAmount",
                "MenuItemID"
                    };

                    foreach (var column in columnsToHide)
                    {
                        if (ManageReservationGridview.Columns.Contains(column))
                        {
                            ManageReservationGridview.Columns[column].Visible = false;
                        }
                    }

                    // Make all columns read-only except for MenuItemName and Quantity
                    foreach (DataGridViewColumn column in ManageReservationGridview.Columns)
                    {
                        if (column.Name != "MenuItemNameComboBox" && column.Name != "Quantity")
                        {
                            column.ReadOnly = true;
                        }
                        else
                        {
                            column.ReadOnly = false;
                        }
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error loading reservations: {ex.Message}");
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

                // Update ItemPrice and MenuItemID when MenuItemNameComboBox changes
                if (e.ColumnIndex == ManageReservationGridview.Columns["MenuItemNameComboBox"].Index)
                {
                    string selectedMenuItemName = ManageReservationGridview.Rows[e.RowIndex].Cells["MenuItemNameComboBox"].Value.ToString();

                    using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
                    {
                        try
                        {
                            string query = "SELECT MenuItemID, ItemPrice FROM Menu WHERE ItemName = @ItemName";
                            SqlCommand cmd = new SqlCommand(query, conn);
                            cmd.Parameters.AddWithValue("@ItemName", selectedMenuItemName);

                            conn.Open();
                            using (SqlDataReader reader = cmd.ExecuteReader())
                            {
                                if (reader.Read())
                                {
                                    // Get the new MenuItemID and ItemPrice
                                    int menuItemID = reader.GetInt32(0);
                                    decimal itemPrice = reader.GetDecimal(1);

                                    // Update MenuItemID and ItemPrice cells
                                    ManageReservationGridview.Rows[e.RowIndex].Cells["MenuItemID"].Value = menuItemID;
                                    ManageReservationGridview.Rows[e.RowIndex].Cells["ItemPrice"].Value = itemPrice;

                                    // Update SubTotal
                                    UpdateSubTotal(e.RowIndex);
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            MessageBox.Show($"Error updating item price: {ex.Message}");
                        }
                    }
                }

                // Update SubTotal if Quantity changes
                if (e.ColumnIndex == ManageReservationGridview.Columns["Quantity"].Index)
                {
                    UpdateSubTotal(e.RowIndex);
                }

                // Update SubTotal if ItemPrice changes
                if (e.ColumnIndex == ManageReservationGridview.Columns["ItemPrice"].Index)
                {
                    UpdateSubTotal(e.RowIndex);
                }
                if (e.ColumnIndex == ManageReservationGridview.Columns["PaidAmount"].Index)
                {
                    // Get the PaymentID and the new PaidAmount
                    int paymentID = Convert.ToInt32(ManageReservationGridview.Rows[e.RowIndex].Cells["PaymentID"].Value);
                    decimal paidAmount = Convert.ToDecimal(ManageReservationGridview.Rows[e.RowIndex].Cells["PaidAmount"].Value);

                    // Call method to update PaidAmount in Payments and DailyPayments tables
                    UpdatePaidAmount(paymentID, paidAmount);
                }
            }
        }

        // Method to update PaidAmount in both Payments and DailyPayments tables
        private void UpdatePaidAmount(int paymentID, decimal paidAmount)
        {
            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    conn.Open();

                    // Update PaidAmount in Payments table
                    string updatePaymentsQuery = @"
                UPDATE Payments
                SET PaidAmount = @PaidAmount
                WHERE PaymentID = @PaymentID";

                    using (SqlCommand cmd = new SqlCommand(updatePaymentsQuery, conn))
                    {
                        cmd.Parameters.AddWithValue("@PaidAmount", paidAmount);
                        cmd.Parameters.AddWithValue("@PaymentID", paymentID);

                        cmd.ExecuteNonQuery();
                    }

                    // Update PaidAmount in DailyPayments table
                    string updateDailyPaymentsQuery = @"
                UPDATE DailyPayments
                SET PaidAmount = @PaidAmount
                WHERE PaymentID = @PaymentID";

                    using (SqlCommand cmd = new SqlCommand(updateDailyPaymentsQuery, conn))
                    {
                        cmd.Parameters.AddWithValue("@PaidAmount", paidAmount);
                        cmd.Parameters.AddWithValue("@PaymentID", paymentID);

                        cmd.ExecuteNonQuery();
                    }

                    MessageBox.Show("PaidAmount updated successfully " +
                        "" +
                        "", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error updating PaidAmount: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }

        private void UpdateSubTotal(int rowIndex)
        {
            try
            {
                // Get Quantity and ItemPrice cells
                DataGridViewCell quantityCell = ManageReservationGridview.Rows[rowIndex].Cells["Quantity"];
                DataGridViewCell itemPriceCell = ManageReservationGridview.Rows[rowIndex].Cells["ItemPrice"];
                DataGridViewCell subTotalCell = ManageReservationGridview.Rows[rowIndex].Cells["SubTotal"];

                // Parse values and calculate SubTotal
                if (decimal.TryParse(quantityCell.Value?.ToString(), out decimal quantity) &&
                    decimal.TryParse(itemPriceCell.Value?.ToString(), out decimal itemPrice))
                {
                    subTotalCell.Value = quantity * itemPrice;
                }
                else
                {
                    subTotalCell.Value = DBNull.Value; // Clear SubTotal if values are invalid
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error updating subtotal: {ex.Message}");
            }
        }





        private void UpdateCustomerId(string customerName, string customerPhoneNumber)
        {
            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                conn.Open();

                // Ensure we're only updating Name and PhoneNumber, not CustomerID
                string query = @"
            UPDATE Customer
            SET Name = @CustomerName, PhoneNumber = @PhoneNumber
            WHERE CustomerID = (
                SELECT TOP 1 CustomerID
                FROM Customer
                WHERE Name = @CustomerName AND PhoneNumber = @PhoneNumber
            )";

                using (SqlCommand cmd = new SqlCommand(query, conn))
                {
                    cmd.Parameters.AddWithValue("@CustomerName", customerName);
                    cmd.Parameters.AddWithValue("@PhoneNumber", customerPhoneNumber);

                    int rowsAffected = cmd.ExecuteNonQuery();

                    if (rowsAffected == 0)
                    {
                        throw new Exception("No matching record found to update.");
                    }
                }
            }
        }

        private void updatebtn_Click(object sender, EventArgs e)
        {
            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    conn.Open();
                    foreach (DataGridViewRow row in ManageReservationGridview.Rows)
                    {
                        if (row.IsNewRow) continue; // Skip new row placeholder

                        // Get cell values, checking for DBNull
                        int reservationID = row.Cells["ReservationID"].Value != DBNull.Value ? Convert.ToInt32(row.Cells["ReservationID"].Value) : 0;
                        int menuItemID = row.Cells["MenuItemID"].Value != DBNull.Value ? Convert.ToInt32(row.Cells["MenuItemID"].Value) : 0;
                        decimal itemPrice = row.Cells["ItemPrice"].Value != DBNull.Value ? Convert.ToDecimal(row.Cells["ItemPrice"].Value) : 0m;
                        int quantity = row.Cells["Quantity"].Value != DBNull.Value ? Convert.ToInt32(row.Cells["Quantity"].Value) : 0;
                        string menuItemName = row.Cells["MenuItemNameComboBox"].Value?.ToString() ?? "N/A";



                        decimal totalAmount = row.Cells["Totalamount"].Value != DBNull.Value ? Convert.ToDecimal(row.Cells["Totalamount"].Value) : 0m;

                        // Check if totalAmount is 0 or invalid (e.g., DBNull)
                        if (totalAmount == 0)
                        {
                            MessageBox.Show("لا يمكن اضافه العنصر .", "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                            return; // Skip this row and move to the next one
                        }
                        // Calculate SubTotal
                        decimal subTotal = quantity * itemPrice;

                        // Update query with change detection
                        string query = @"
                    UPDATE OrderDetails
                    SET MenuItemID = @MenuItemID, 
                        Quantity = @Quantity, 
                        ItemPrice = @ItemPrice 
                    WHERE ReservationID = @ReservationID AND OrderDetailID = @OrderDetailID
                      AND (MenuItemID <> @MenuItemID OR Quantity <> @Quantity OR ItemPrice <> @ItemPrice)";

                        int rowsAffected = 0;

                        using (SqlCommand cmd = new SqlCommand(query, conn))
                        {
                            // Set query parameters
                            cmd.Parameters.AddWithValue("@MenuItemID", menuItemID);
                            cmd.Parameters.AddWithValue("@Quantity", quantity);
                            cmd.Parameters.AddWithValue("@ItemPrice", itemPrice);
                            cmd.Parameters.AddWithValue("@ReservationID", reservationID);
                            cmd.Parameters.AddWithValue("@OrderDetailID", row.Cells["OrderDetailID"].Value);

                            // Execute update and check the number of rows affected
                            rowsAffected = cmd.ExecuteNonQuery();
                        }

                        // Only log if a row was actually updated
                        if (rowsAffected > 0)
                        {
                            // Build the descriptive action message
                            string action = $"User: {_username} Edited ReservationID: {reservationID}, " +
                                            $"MenuItemName: {menuItemName}, ItemPrice: {itemPrice}, " +
                                            $"Quantity: {quantity} , Edit Order";

                            // Log the action into UserLog
                            string logQuery = "INSERT INTO UserLog (CashierName, Action) VALUES (@CashierName, @Action)";

                            using (SqlCommand cmd = new SqlCommand(logQuery, conn))
                            {
                                cmd.Parameters.AddWithValue("@CashierName", _username);
                                cmd.Parameters.AddWithValue("@Action", action);

                                cmd.ExecuteNonQuery();
                            }
                        }
                    }

                    MessageBox.Show("Records updated successfully!", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error updating records: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }




        // Helper method to get MenuItemName based on MenuItemID
        private string GetMenuItemName(int menuItemID, SqlConnection conn)
        {
            if (conn == null || conn.State != ConnectionState.Open)
            {
                throw new InvalidOperationException("Connection is not open.");
            }

            string menuItemName = string.Empty;
            string query = "SELECT ItemName FROM Menu WHERE MenuItemID = @MenuItemID";

            using (SqlCommand cmd = new SqlCommand(query, conn))
            {
                cmd.Parameters.AddWithValue("@MenuItemID", menuItemID);

                try
                {
                    var result = cmd.ExecuteScalar();
                    menuItemName = result != null ? result.ToString() : string.Empty;
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error executing SQL: {ex.Message}", "SQL Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    menuItemName = string.Empty; // Fallback to empty string in case of error
                }
            }

            return menuItemName;
        }



        private void button1_Click(object sender, EventArgs e)
        {
            EditCustomerData editCustomerData = new EditCustomerData(_username);
            this.Hide();
            editCustomerData.ShowDialog();
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

        private void Editorder_Load_1(object sender, EventArgs e)
        {

            //cashiernamelabel.Text = _username;
        }

        private void button6_Click(object sender, EventArgs e)
        {
            Home home = new Home(_username);
            this.Hide();
            home.ShowDialog();
            this.Close();
        }

     
      
        private void deletebtn_Click(object sender, EventArgs e)
        {
            // Get the currently selected row from the DataGridView
            DataGridViewRow selectedRow = ManageReservationGridview.CurrentRow;

            if (selectedRow == null)
            {
                MessageBox.Show("Please select a row to delete.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    conn.Open();

                    // Get cell values, checking for DBNull
                    int reservationID = selectedRow.Cells["ReservationID"].Value != DBNull.Value ? Convert.ToInt32(selectedRow.Cells["ReservationID"].Value) : 0;
                    int menuItemID = selectedRow.Cells["MenuItemID"].Value != DBNull.Value ? Convert.ToInt32(selectedRow.Cells["MenuItemID"].Value) : 0;
                    decimal itemPrice = selectedRow.Cells["ItemPrice"].Value != DBNull.Value ? Convert.ToDecimal(selectedRow.Cells["ItemPrice"].Value) : 0m;
                    int quantity = selectedRow.Cells["Quantity"].Value != DBNull.Value ? Convert.ToInt32(selectedRow.Cells["Quantity"].Value) : 0;
                    string menuItemName = selectedRow.Cells["MenuItemNameComboBox"].Value?.ToString() ?? "N/A";

                    // Check if OrderDetailID is DBNull or invalid
                    object orderDetailIDObj = selectedRow.Cells["OrderDetailID"].Value;
                    if (orderDetailIDObj == DBNull.Value || orderDetailIDObj == null)
                    {
                        MessageBox.Show("OrderDetailID is missing for this row. Skipping delete.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        return;
                    }

                    int orderDetailID = Convert.ToInt32(orderDetailIDObj);

                    // Delete query
                    string query = "DELETE FROM OrderDetails WHERE OrderDetailID = @OrderDetailID";

                    int rowsAffected = 0;

                    using (SqlCommand cmd = new SqlCommand(query, conn))
                    {
                        // Set query parameters
                        cmd.Parameters.AddWithValue("@OrderDetailID", orderDetailID);

                        // Execute delete command
                        rowsAffected = cmd.ExecuteNonQuery();
                    }
                    LoadReservations(); // Refresh the data after deletion
                    // Log only if a row was actually deleted
                    if (rowsAffected > 0)
                    {
                        // Build the descriptive action message
                        string action = $"User: {_username} Deleted ReservationID: {reservationID}, " +
                                        $"MenuItemName: {menuItemName}, ItemPrice: {itemPrice}, " +
                                        $"Quantity: {quantity} , Deleted Item";

                        // Log the action into UserLog
                        string logQuery = "INSERT INTO UserLog (CashierName, Action) VALUES (@CashierName, @Action)";

                        using (SqlCommand cmd = new SqlCommand(logQuery, conn))
                        {
                            cmd.Parameters.AddWithValue("@CashierName", _username);
                            cmd.Parameters.AddWithValue("@Action", action);

                            cmd.ExecuteNonQuery();
                        }

                        MessageBox.Show("Record deleted successfully!", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
                        
                    }
                    else
                    {
                        MessageBox.Show($"No rows were deleted for OrderDetailID: {orderDetailID}. It may not exist.", "Info", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error deleting record: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }


        private void backkbtn_Click(object sender, EventArgs e)
        {
            Addorders navigation = new Addorders(_username);
            this.Hide();
            navigation.ShowDialog();
            this.Close();
        }

        private void filteringTxtBox_TextChanged(object sender, EventArgs e)
        {

        }
    }
}
