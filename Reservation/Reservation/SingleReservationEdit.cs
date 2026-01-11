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
    public partial class SingleReservationEdit : Form
    {
        private string _username;



        private float _initialFormWidth;
        private float _initialFormHeight;
        private ControlInfo[] _controlsInfo;

        public SingleReservationEdit(string username)
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

        private void Editorder_Load(object sender, EventArgs e)
        {
            // Load reservation data when the form loads
            LoadReservations();
        }

        private void LoadReservations()
        {
            if (dateTimePicker != null)
            {
                ManageReservationGridview.Controls.Remove(dateTimePicker);
                dateTimePicker.Dispose();
                dateTimePicker = null;
            }
            // Get the filter value from the TextBox
            string filterValue = filteringTxtBox.Text.Trim();

            // If the TextBox is empty, do nothing
            if (string.IsNullOrEmpty(filterValue))
            {
                ManageReservationGridview.DataSource = null; // Clear the DataGridView
                return;
            }

            string reservationsQuery = @"
    SELECT 
        r.ReservationID, 
        c.Name AS CustomerName, 
        r.RestaurantID, 
        rest.Name AS RestaurantName, 
        r.ReservationDate, 
        r.NumberOfGuests,
        r.Notes,
        r.Important,
        r.TotalPrice, 
        r.DateSubmitted,
        r.Cashiername
    FROM Reservations r
    INNER JOIN Customer c ON r.CustomerID = c.CustomerID
    INNER JOIN Restaurant rest ON r.RestaurantID = rest.RestaurantID

    WHERE Reservationid = @ReservationId 
    ORDER BY r.ReservationID DESC"; // Order by ReservationID in descending order

            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    // Fetch reservation data
                    SqlDataAdapter reservationsAdapter = new SqlDataAdapter(reservationsQuery, conn);
                    reservationsAdapter.SelectCommand.Parameters.AddWithValue("@ReservationId", filterValue);
                    DataTable reservationsTable = new DataTable();
                    reservationsAdapter.Fill(reservationsTable);
                    
                    // Fetch restaurant data for the ComboBox
                    string restaurantQuery = "SELECT RestaurantID, Name FROM Restaurant";
                    SqlDataAdapter restaurantAdapter = new SqlDataAdapter(restaurantQuery, conn);
                    DataTable restaurantTable = new DataTable();
                    restaurantAdapter.Fill(restaurantTable);

                    // Bind reservation data to the DataGridView
                    ManageReservationGridview.DataSource = reservationsTable;

                    // Add ComboBox column for Restaurant
                    if (!ManageReservationGridview.Columns.Contains("RestaurantColumn"))
                    {
                        DataGridViewComboBoxColumn restaurantColumn = new DataGridViewComboBoxColumn
                        {
                            Name = "RestaurantColumn",
                            HeaderText = "Restaurant",
                            DataSource = restaurantTable,
                            DisplayMember = "Name",
                            ValueMember = "RestaurantID",
                            DataPropertyName = "RestaurantID",
                            AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill
                        };
                        ManageReservationGridview.Columns.Insert(
                            ManageReservationGridview.Columns["RestaurantName"].Index, restaurantColumn);
                        ManageReservationGridview.Columns.Remove("RestaurantName");
                    }

                    // Hide the RestaurantID column
                    if (ManageReservationGridview.Columns.Contains("RestaurantID"))
                    {
                        ManageReservationGridview.Columns["RestaurantID"].Visible = false;

                    }


                    // Hide the RestaurantID column
                    if (ManageReservationGridview.Columns.Contains("RestaurantName"))
                    {
                        ManageReservationGridview.Columns["RestaurantName"].Visible = false;

                    }

                    // Add a DateTimePicker column for ReservationDate
                    if (!ManageReservationGridview.Columns.Contains("ReservationDatePicker"))
                    {
                        DataGridViewTextBoxColumn reservationDateColumn = new DataGridViewTextBoxColumn
                        {
                            Name = "ReservationDatePicker",
                            HeaderText = "Reservation Date",
                            DataPropertyName = "ReservationDate",
                            AutoSizeMode = DataGridViewAutoSizeColumnMode.AllCells
                        };
                        ManageReservationGridview.Columns.Insert(
                            ManageReservationGridview.Columns["ReservationDate"].Index, reservationDateColumn);
                        ManageReservationGridview.Columns.Remove("ReservationDate");
                    }

                    // Configure column properties
                    foreach (DataGridViewColumn column in ManageReservationGridview.Columns)
                    {
                        if (column.Name == "RestaurantColumn" ||
                            column.Name == "ReservationDatePicker" ||
                            column.Name == "NumberOfGuests" ||
                            column.Name == "Notes" ||
                            column.Name == "Important")
                        {
                            column.ReadOnly = false; // Allow editing
                        }
                        else
                        {
                            column.ReadOnly = true; // Make other columns read-only
                        }
                    }

                    // Add event to show DateTimePicker
                    ManageReservationGridview.CellClick += ManageReservationGridview_CellClick;
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error loading reservations: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }


        private DateTimePicker dateTimePicker; // Declare a DateTimePicker at the class level for reuse

        private void ManageReservationGridview_CellClick(object sender, DataGridViewCellEventArgs e)
        {
            // Ensure the click is on a valid cell
            if (e.RowIndex < 0 || e.ColumnIndex < 0) return;

            // Ensure the click is on the ReservationDatePicker column
            var columnName = ManageReservationGridview.Columns[e.ColumnIndex].Name;
            if (columnName != "ReservationDatePicker") return;

            // Remove any existing DateTimePicker
            if (dateTimePicker != null)
            {
                ManageReservationGridview.Controls.Remove(dateTimePicker);
                dateTimePicker.Dispose();
                dateTimePicker = null;
            }

            // Create and configure the DateTimePicker
            dateTimePicker = new DateTimePicker
            {
                Format = DateTimePickerFormat.Short,
                Visible = true
            };

            // Get the cell rectangle to position the DateTimePicker
            Rectangle cellRectangle = ManageReservationGridview.GetCellDisplayRectangle(e.ColumnIndex, e.RowIndex, true);
            dateTimePicker.Size = new Size(cellRectangle.Width, cellRectangle.Height);
            dateTimePicker.Location = new Point(cellRectangle.X, cellRectangle.Y);

            // Set the DateTimePicker value to the cell's current value (if valid)
            object cellValue = ManageReservationGridview.Rows[e.RowIndex].Cells[e.ColumnIndex].Value;
            if (cellValue != null && DateTime.TryParse(cellValue.ToString(), out DateTime cellDate))
            {
                dateTimePicker.Value = cellDate;
            }
            else
            {
                dateTimePicker.Value = DateTime.Today; // Default to today's date
            }

            // Handle the value change event
            dateTimePicker.ValueChanged += (s, ev) =>
            {
                ManageReservationGridview.Rows[e.RowIndex].Cells[e.ColumnIndex].Value = dateTimePicker.Value;
            };

            // Add and show the DateTimePicker
            ManageReservationGridview.Controls.Add(dateTimePicker);
            dateTimePicker.BringToFront();
            dateTimePicker.Focus();
        }



        // This method will handle the search button click
        private void loadbtn_Click(object sender, EventArgs e)
        {



            LoadReservations();
        }


        private HashSet<int> editedRows = new HashSet<int>();


       

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
                    if (ManageReservationGridview.CurrentRow == null || ManageReservationGridview.CurrentRow.IsNewRow)
                    {
                        MessageBox.Show("Please select a valid row to update.", "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                        return;
                    }

                    conn.Open();

                    // Get the selected row
                    DataGridViewRow row = ManageReservationGridview.CurrentRow;

                    // Retrieve editable values
                    int reservationID = Convert.ToInt32(row.Cells["ReservationID"].Value);

                    // Validate and retrieve the selected restaurant ID from the ComboBox column
                    if (row.Cells["RestaurantColumn"].Value == null)
                    {
                        MessageBox.Show("Please select a valid restaurant.", "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                        return;
                    }

                    int restaurantID = Convert.ToInt32(row.Cells["RestaurantColumn"].Value);
                    int newNumberOfGuests = Convert.ToInt32(row.Cells["NumberOfGuests"].Value);
                    DateTime reservationDate = Convert.ToDateTime(row.Cells["ReservationDatePicker"].Value);
                    string notes = row.Cells["Notes"].Value.ToString();
                    string important = row.Cells["important"].Value.ToString();

                    // Check if the user's role is not 1 or 5
                    if (GlobalUser.Role != 1 && GlobalUser.Role != 5)
                    {
                        // Query to get the current number of guests in the reservation
                        string currentGuestsQuery = @"
                SELECT NumberOfGuests
                FROM Reservations
                WHERE ReservationID = @ReservationID";

                        int currentNumberOfGuests = 0;
                        using (SqlCommand currentGuestsCmd = new SqlCommand(currentGuestsQuery, conn))
                        {
                            currentGuestsCmd.Parameters.AddWithValue("@ReservationID", reservationID);
                            currentNumberOfGuests = Convert.ToInt32(currentGuestsCmd.ExecuteScalar());
                        }

                        // Calculate the difference between the new and current number of guests
                        int guestDifference = newNumberOfGuests - currentNumberOfGuests;

                        // Query to check remaining capacity
                        string capacityQuery = @"
                SELECT RemainingCapacity
                FROM RestaurantDailyCapacity
                WHERE RestaurantID = @RestaurantID
                  AND Date = @ReservationDate";

                        using (SqlCommand capacityCmd = new SqlCommand(capacityQuery, conn))
                        {
                            capacityCmd.Parameters.AddWithValue("@RestaurantID", restaurantID);
                            capacityCmd.Parameters.AddWithValue("@ReservationDate", reservationDate);

                            int remainingCapacity = Convert.ToInt32(capacityCmd.ExecuteScalar());

                            // Check if the remaining capacity can accommodate the guest difference
                            if (remainingCapacity - guestDifference < 0)
                            {
                                MessageBox.Show($"Cannot update reservation. The remaining capacity would be negative. You can add up to {remainingCapacity + currentNumberOfGuests} guests.", "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                                return;
                            }
                        }
                    }

                    // Update query
                    string updateQuery = @"
            UPDATE Reservations
            SET 
                RestaurantID = @RestaurantID,
                NumberOfGuests = @NumberOfGuests,
                ReservationDate = @ReservationDate,
                Notes = @Notes,
                Important = @Important
            WHERE 
                ReservationID = @ReservationID";

                    using (SqlCommand cmd = new SqlCommand(updateQuery, conn))
                    {
                        // Add parameters
                        cmd.Parameters.AddWithValue("@ReservationID", reservationID);
                        cmd.Parameters.AddWithValue("@RestaurantID", restaurantID);
                        cmd.Parameters.AddWithValue("@NumberOfGuests", newNumberOfGuests);
                        cmd.Parameters.AddWithValue("@ReservationDate", reservationDate);
                        cmd.Parameters.AddWithValue("@Notes", notes);
                        cmd.Parameters.AddWithValue("@Important", important);

                        // Execute the update
                        cmd.ExecuteNonQuery();
                    }

                    string Resturantname = row.Cells["RestaurantColumn"].FormattedValue?.ToString() ?? "N/A"; // Get the display name of the restaurant

                    // Build the descriptive action message
                    string action = $"Edited ReservationID: {reservationID}, " +
                                          $" Resturant: {Resturantname}, " +
                                         $" Quantity: {newNumberOfGuests}, " +
                                         $"ReservationDate: {reservationDate} , Edited Reservation";

                    // Log the action into UserLog
                    string logQuery = "INSERT INTO UserLog (CashierName, Action) VALUES (@CashierName, @Action)";

                    using (SqlCommand cmd = new SqlCommand(logQuery, conn))
                    {
                        cmd.Parameters.AddWithValue("@CashierName", _username);
                        cmd.Parameters.AddWithValue("@Action", action);

                        cmd.ExecuteNonQuery();
                    }

                    LoadReservations();

                    MessageBox.Show("Reservation updated successfully!", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error updating reservation: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
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
            // Get the Reservation ID from the TextBox
            if (int.TryParse(filteringTxtBox.Text, out int reservationID))
            {
                // Ask the user for confirmation
                var confirmationResult = MessageBox.Show(
                    $"Are you sure you want to delete Reservation ID {reservationID}?",
                    "Confirm Deletion",
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Warning);

                // If the user presses No, return without deleting
                if (confirmationResult == DialogResult.No)
                {
                    return;
                }

                // Ask for notes if the user confirms
                string notes = string.Empty;
                using (var inputForm = new Form())
                {
                    inputForm.Text = "سبب مسح الحجز";
                    inputForm.Width = 400;
                    inputForm.Height = 200;
                    inputForm.StartPosition = FormStartPosition.CenterParent;

                    Label label = new Label() { Text = "Enter notes (optional):", Dock = DockStyle.Top, Padding = new Padding(10) };
                    TextBox notesTextBox = new TextBox() { Multiline = true, Dock = DockStyle.Fill };
                    Button submitButton = new Button() { Text = "OK", Dock = DockStyle.Bottom };
                    submitButton.Click += (s, eArgs) => inputForm.DialogResult = DialogResult.OK;

                    inputForm.Controls.Add(notesTextBox);
                    inputForm.Controls.Add(submitButton);
                    inputForm.Controls.Add(label);

                    if (inputForm.ShowDialog() == DialogResult.OK)
                    {
                        notes = notesTextBox.Text.Trim();
                    }
                    else
                    {
                        // User canceled notes input
                        return;
                    }
                }

                // Get the CashierName from the _username variable (you should already have this variable)
                string cashierName = _username; // Replace _username with the actual variable holding the username

                try
                {
                    using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                    {
                        connection.Open();

                        // Create a SqlCommand to execute the DeleteReservationAndRelatedData stored procedure
                        using (SqlCommand command = new SqlCommand("DeleteReservationAndRelatedData", connection))
                        {
                            command.CommandType = CommandType.StoredProcedure;

                            // Add the parameters to the stored procedure
                            command.Parameters.AddWithValue("@ReservationID", reservationID);
                            command.Parameters.AddWithValue("@CashierName", cashierName);
                            command.Parameters.AddWithValue("@Notes", string.IsNullOrEmpty(notes) ? (object)DBNull.Value : notes);


                            // Execute the stored procedure
                            int rowsAffected = command.ExecuteNonQuery();

                            // Inform the user
                            if (rowsAffected > 0)
                            {

                                string logQuery = "INSERT INTO UserLog (CashierName, Action, DateAndTime) VALUES (@CashierName, @Action, GETDATE())";
                                using (SqlCommand logCommand = new SqlCommand(logQuery, connection))
                                {
                                    string logDetails = $"Deleted Reservation ID: {filteringTxtBox.Text} , Deleted Reservation";
                                    logCommand.Parameters.AddWithValue("@CashierName", _username);
                                    logCommand.Parameters.AddWithValue("@Action", logDetails);
                                    logCommand.ExecuteNonQuery();
                                }



                                MessageBox.Show("Reservation and related data deleted successfully.", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);

                                // Optionally, clear the TextBox after deletion
                                filteringTxtBox.Clear();

                                // Refresh any related UI or data grid to reflect changes
                                LoadReservations();
                            }
                            else
                            {
                                MessageBox.Show("No reservation found with the provided ID.", "Not Found", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                            }
                        }
                    }
                }
                catch (SqlException sqlEx)
                {
                    MessageBox.Show($"Database error: {sqlEx.Message}", "SQL Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"An unexpected error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
            else
            {
                MessageBox.Show("Please enter a valid numeric Reservation ID.", "Invalid Input", MessageBoxButtons.OK, MessageBoxIcon.Warning);
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

        private void ManageReservationGridview_CellContentClick(object sender, DataGridViewCellEventArgs e)
        {

        }

       
    }
}
