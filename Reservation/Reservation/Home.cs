using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Data.SqlClient;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Printing;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;




namespace Reservation
{
    public partial class Home : Form
    {



        private float _initialFormWidth;
        private float _initialFormHeight;
        private ControlInfo[] _controlsInfo;

        private string _username;
        public Home(string username)
        {
            InitializeComponent();

            PopulateMenuItems();
            reservationdateandtime.Value = DateTime.Now;
            Resturantnamecombo.Enabled = false; // Disable combobox until a date is selected

            nametxt.TextChanged += new EventHandler(nametxt_TextChanged);
           
           

            // Set event handler for form resize
          


            // Configure autocomplete for the name TextBox
          

            // Event handlers
            ConfigureNameAutoComplete();

            nametxt.TextChanged += nametxt_TextChanged;
            nametxt.Leave += nametxt_Leave;



            Phonenumbertxt.MaxLength = 11; // Ensure no more than 11 characters

            Phonenumbertxt.KeyPress += Phonenumbertxt_KeyPress;
            Phonenumbertxt.TextChanged += Phonenumbertxt_TextChanged;
            Phonenumbertxt.Leave += Phonenumbertxt_Leave;
            ConfigureAutoComplete();
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

        private System.Threading.Timer clockTimer;

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
            Application.Exit();
        }

        private void logout_btn_Click(object sender, EventArgs e)
        {
            DialogResult check = MessageBox.Show("Are you sure you want to logout?"
                , "Confirmation Message", MessageBoxButtons.YesNo, MessageBoxIcon.Question);

            if (check == DialogResult.Yes)
            {
              
            }
        }

        private void dashboard_btn_Click(object sender, EventArgs e)
        {
            

           

        }

        private void addEmployee_btn_Click(object sender, EventArgs e)
        {
            

           

        }

        private void salary_btn_Click(object sender, EventArgs e)
        {
           

            

        }


        private void Phonenumbertxt_TextChanged(object sender, EventArgs e)
        {
            // Remove non-numeric characters
         
        }

        private void LockCustomerFields()
        {
            nametxt.Enabled = false;
            Phonenumbertxt.Enabled = false;
           
        }
















        private void addnewcustomerbtn_Click(object sender, EventArgs e)
        {
            string customerName = nametxt.Text.Trim();
            string phoneNumber = Phonenumbertxt.Text.Trim();

            // Validate Customer Name and Phone Number
            if (string.IsNullOrWhiteSpace(customerName) || string.IsNullOrWhiteSpace(phoneNumber))
            {
                MessageBox.Show("Please fill in both Customer Name and Phone Number.", "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // Validate Phone Number Length
            if (phoneNumber.Length != 11 || !phoneNumber.All(char.IsDigit))
            {
                MessageBox.Show("رقم التليفون غير كامل", "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            try
            {
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    connection.Open();

                    // Check if the customer name or phone number already exists in the database
                    string checkQuery = "SELECT COUNT(*) FROM Customer WHERE Name = @Name OR PhoneNumber = @PhoneNumber";
                    using (SqlCommand checkCommand = new SqlCommand(checkQuery, connection))
                    {
                        checkCommand.Parameters.AddWithValue("@Name", customerName);
                        checkCommand.Parameters.AddWithValue("@PhoneNumber", phoneNumber);

                        int customerCount = (int)checkCommand.ExecuteScalar(); // Returns the count of matching rows

                        if (customerCount > 0)
                        {
                            // Customer already exists
                            MessageBox.Show("A customer with this name or phone number already exists.", "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                            return; // Prevent insertion
                        }
                    }

                    // If customer doesn't exist, proceed with adding the new customer
                    string insertQuery = "INSERT INTO Customer (Name, PhoneNumber) VALUES (@Name, @PhoneNumber)";
                    using (SqlCommand insertCommand = new SqlCommand(insertQuery, connection))
                    {
                        insertCommand.Parameters.AddWithValue("@Name", customerName);
                        insertCommand.Parameters.AddWithValue("@PhoneNumber", phoneNumber);

                        int rowsAffected = insertCommand.ExecuteNonQuery();
                        if (rowsAffected > 0)
                        {
                            MessageBox.Show("Customer added successfully!", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
                            addnewcustomerbtn.Enabled = false;
                            LockCustomerFields(); // Make fields readonly
                        }
                        else
                        {
                            MessageBox.Show("Failed to add customer.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }


        private void reservationnumberlabel_Click(object sender, EventArgs e)
        {

        }

        private void reservationdateandtime_ValueChanged(object sender, EventArgs e)
        {

            if (GlobalUser.Role == 1 || GlobalUser.Role == 5)
            {
                LoadAvailableRestaurants();
                Resturantnamecombo.Text = "";

            }
            else {
                LoadAvailableRestaurantss();

                Resturantnamecombo.Text = "";
            }
        }


        private void LoadAvailableRestaurantss()
        {

            if (GlobalUser.Role != 1)
            {
                // Clear existing items
                Resturantnamecombo.Items.Clear();

                // Variable to hold the restaurant list to show in the label
                string restaurantInfo = "";

                // Load data from the database
                DateTime selectedDate = reservationdateandtime.Value.Date;

                try
                {
                    using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                    {
                        connection.Open();
                        string query = @"
            SELECT r.RestaurantID, r.Name, rd.RemainingCapacity
            FROM Restaurant r
            INNER JOIN RestaurantDailyCapacity rd ON r.RestaurantID = rd.RestaurantID
            WHERE rd.Date = @SelectedDate AND RemainingCapacity > 0 ";

                        using (SqlCommand command = new SqlCommand(query, connection))
                        {
                            command.Parameters.AddWithValue("@SelectedDate", selectedDate);

                            using (SqlDataReader reader = command.ExecuteReader())
                            {
                                // Loop through all available restaurants and add to ComboBox
                                while (reader.Read())
                                {
                                    ComboboxItem item = new ComboboxItem
                                    {
                                        Text = reader["Name"].ToString(),  // Restaurant Name
                                        Value = Convert.ToInt32(reader["RestaurantID"]),  // Restaurant ID
                                        RemainingCapacity = Convert.ToInt32(reader["RemainingCapacity"])  // Remaining Capacity
                                    };
                                    Resturantnamecombo.Items.Add(item);  // Add the item to ComboBox

                                    // Append the restaurant name and remaining capacity to the label string
                                    restaurantInfo += $"{item.Text}: {item.RemainingCapacity} capacity available\n";
                                }
                            }
                        }
                    }

                    // Enable the ComboBox if we have any restaurants
                    Resturantnamecombo.Enabled = Resturantnamecombo.Items.Count > 0;

                    if (Resturantnamecombo.Items.Count == 0)
                    {
                        MessageBox.Show("No restaurants with sufficient capacity available for the selected date.", "Information", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    }
                    else
                    {
                        // Update the label with the restaurant info
                        RemainingCapacitylabel.Text = restaurantInfo;
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }

            else
            {


                // Clear existing items
                Resturantnamecombo.Items.Clear();

                // Variable to hold the restaurant list to show in the label
                string restaurantInfo = "";

                // Load data from the database
                DateTime selectedDate = reservationdateandtime.Value.Date;

                try
                {
                    using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                    {
                        connection.Open();
                        string query = @"
            SELECT r.RestaurantID, r.Name, rd.RemainingCapacity
            FROM Restaurant r
            INNER JOIN RestaurantDailyCapacity rd ON r.RestaurantID = rd.RestaurantID
            WHERE rd.Date = @SelectedDate";

                        using (SqlCommand command = new SqlCommand(query, connection))
                        {
                            command.Parameters.AddWithValue("@SelectedDate", selectedDate);

                            using (SqlDataReader reader = command.ExecuteReader())
                            {
                                // Loop through all available restaurants and add to ComboBox
                                while (reader.Read())
                                {
                                    ComboboxItem item = new ComboboxItem
                                    {
                                        Text = reader["Name"].ToString(),  // Restaurant Name
                                        Value = Convert.ToInt32(reader["RestaurantID"]),  // Restaurant ID
                                        RemainingCapacity = Convert.ToInt32(reader["RemainingCapacity"])  // Remaining Capacity
                                    };
                                    Resturantnamecombo.Items.Add(item);  // Add the item to ComboBox

                                    // Append the restaurant name and remaining capacity to the label string
                                    restaurantInfo += $"{item.Text}: {item.RemainingCapacity} capacity available\n";
                                }
                            }
                        }
                    }

                    // Enable the ComboBox if we have any restaurants
                    Resturantnamecombo.Enabled = Resturantnamecombo.Items.Count > 0;

                    if (Resturantnamecombo.Items.Count == 0)
                    {
                        MessageBox.Show("No restaurants with sufficient capacity available for the selected date.", "Information", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    }
                    else
                    {
                        // Update the label with the restaurant info
                        RemainingCapacitylabel.Text = restaurantInfo;
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }



        private void Resturantnamecombo_SelectedIndexChanged(object sender, EventArgs e)
        {
            if (Resturantnamecombo.SelectedIndex != -1)
            {
                // Get the selected item
                ComboboxItem selectedItem = (ComboboxItem)Resturantnamecombo.SelectedItem;

                // Get the RestaurantID from the selected item
                int selectedRestaurantId = selectedItem.Value;

                // Print the Restaurant ID (for debugging purposes)
                Console.WriteLine("Selected RestaurantID: " + selectedRestaurantId);

                // Do whatever you need with the selectedRestaurantId (e.g., store it, make queries, etc.)
            }
        }


        private void capacitytxt_TextChanged(object sender, EventArgs e)
        {

        }



        private void LockReservationFields()
        {
            reservationdateandtime.Enabled = false;
            Resturantnamecombo.Enabled = false;
            capacitytxt.Enabled = false;
            Reservationdatabtn.Enabled = false; 
            importanttxt.Enabled = false;
            addnewcustomerbtn.Enabled = false;
        }

        private void Reservationdatabtn_Click(object sender, EventArgs e)
        {
            // Validate input fields
            if (string.IsNullOrWhiteSpace(capacitytxt.Text) || Resturantnamecombo.SelectedIndex == -1 || reservationdateandtime.Value == null
                || string.IsNullOrWhiteSpace(nametxt.Text) || string.IsNullOrWhiteSpace(Phonenumbertxt.Text))
            {
                MessageBox.Show("Please fill in all the fields.", "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            // Validate requested capacity
            if (!int.TryParse(capacitytxt.Text, out int requestedCapacity) || requestedCapacity <= 0)
            {
                MessageBox.Show("Capacity must be a positive number.", "Validation Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string selectedRestaurantName = Resturantnamecombo.SelectedItem.ToString();
            string customerName = nametxt.Text;
            string phoneNumber = Phonenumbertxt.Text;
            DateTime selectedDate = reservationdateandtime.Value.Date;

            try
            {
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    connection.Open();

                    // Check if the reservation date is valid (not earlier than the server's current date)
                    string checkDateQuery = "SELECT CASE WHEN @ReservationDate >= CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END";
                    using (SqlCommand cmd = new SqlCommand(checkDateQuery, connection))
                    {
                        cmd.Parameters.AddWithValue("@ReservationDate", selectedDate);
                        int isValidDate = Convert.ToInt32(cmd.ExecuteScalar());
                        if (isValidDate == 0)
                        {
                            MessageBox.Show("The reservation date cannot be earlier than today.", "Invalid Date", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                            return;
                        }
                    }

                    // Get RestaurantID
                    string getRestaurantIdQuery = "SELECT RestaurantID FROM Restaurant WHERE Name = @RestaurantName";
                    int restaurantId = 0;
                    using (SqlCommand cmd = new SqlCommand(getRestaurantIdQuery, connection))
                    {
                        cmd.Parameters.AddWithValue("@RestaurantName", selectedRestaurantName);
                        object result = cmd.ExecuteScalar();
                        if (result != null)
                            restaurantId = Convert.ToInt32(result);
                        else
                        {
                            MessageBox.Show("Restaurant not found.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                            return;
                        }
                    }

                    // Get CustomerID
                    string getCustomerIdQuery = "SELECT CustomerID FROM Customer WHERE Name = @CustomerName AND PhoneNumber = @PhoneNumber";
                    int customerId = 0;
                    using (SqlCommand cmd = new SqlCommand(getCustomerIdQuery, connection))
                    {
                        cmd.Parameters.AddWithValue("@CustomerName", customerName);
                        cmd.Parameters.AddWithValue("@PhoneNumber", phoneNumber);
                        object result = cmd.ExecuteScalar();
                        if (result != null)
                            customerId = Convert.ToInt32(result);
                        else
                        {
                            MessageBox.Show("Customer not found.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                            return;
                        }
                    }

                    // Check remaining capacity
                    string checkCapacityQuery = @"
                SELECT RemainingCapacity 
                FROM RestaurantDailyCapacity 
                WHERE RestaurantID = @RestaurantID AND Date = @Date";
                    int remainingCapacity = 0;
                    using (SqlCommand cmd = new SqlCommand(checkCapacityQuery, connection))
                    {
                        cmd.Parameters.AddWithValue("@RestaurantID", restaurantId);
                        cmd.Parameters.AddWithValue("@Date", selectedDate);
                        object result = cmd.ExecuteScalar();
                        if (result != null)
                            remainingCapacity = Convert.ToInt32(result);
                        else
                        {
                            MessageBox.Show("No capacity record found for the selected restaurant and date.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                            return;
                        }
                    }
                    if (GlobalUser.Role != 1 && GlobalUser.Role != 5) {

                        if (remainingCapacity < requestedCapacity)
                        {
                            MessageBox.Show($"Insufficient capacity. Only {remainingCapacity} seats are available.", "Capacity Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                            return;
                        }
                    }
                    

                    // Insert reservation and get the ReservationID
                    string insertReservationQuery = @"
                INSERT INTO Reservations (CustomerID, RestaurantID, ReservationDate, [NumberOfGuests], DateSubmitted, CashierName)
                VALUES (@CustomerID, @RestaurantID, @Date, @Capacity, @DateSubmitted, @CashierName);
                SELECT SCOPE_IDENTITY();";
                    int reservationId = 0;
                    using (SqlCommand cmd = new SqlCommand(insertReservationQuery, connection))
                    {
                        cmd.Parameters.AddWithValue("@CustomerID", customerId);
                        cmd.Parameters.AddWithValue("@RestaurantID", restaurantId);
                        cmd.Parameters.AddWithValue("@Date", selectedDate);
                        cmd.Parameters.AddWithValue("@Capacity", requestedCapacity);
                        cmd.Parameters.AddWithValue("@CashierName", _username);
                        cmd.Parameters.AddWithValue("@DateSubmitted", DateTime.Parse(DatenTimetxt.Text));

                        object result = cmd.ExecuteScalar();
                        if (result != null)
                        {
                            reservationId = Convert.ToInt32(result);
                            MessageBox.Show("Reservation successfully saved.", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);

                            // Update the reservation number label
                            reservationnumberlabel.Text = $"Reservation number is = {reservationId}";
                            reservationnumberlabel.ForeColor = Color.Red;
                            reservationidtxt.Text = reservationId.ToString();

                            if (GlobalUser.Role != 1 && GlobalUser.Role != 5)
                            {

                                LoadAvailableRestaurantss();
                            }// Update TextBox
                            else
                            {
                                LoadAvailableRestaurants();
                            }
                            LockReservationFields();
                            LockCustomerFields();

                        }
                        else
                        {
                            MessageBox.Show("Failed to save the reservation.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        }
                    }

                    // Update Notes in Reservation
                    string updateImportantQuery = "UPDATE Reservations SET important = @important WHERE ReservationID = @ReservationID";
                    using (SqlCommand updateNotesCommand = new SqlCommand(updateImportantQuery, connection))
                    {
                        updateNotesCommand.Parameters.AddWithValue("@important", importanttxt.Text.Trim());
                        updateNotesCommand.Parameters.AddWithValue("@ReservationID", reservationId);
                        updateNotesCommand.ExecuteNonQuery();
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }





        private void LoadAvailableRestaurants()
        {

            if (GlobalUser.Role != 1)
            {
                // Clear existing items
                Resturantnamecombo.Items.Clear();

                // Variable to hold the restaurant list to show in the label
                string restaurantInfo = "";

                // Load data from the database
                DateTime selectedDate = reservationdateandtime.Value.Date;

                try
                {
                    using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                    {
                        connection.Open();
                        string query = @"
            SELECT r.RestaurantID, r.Name, rd.RemainingCapacity
            FROM Restaurant r
            INNER JOIN RestaurantDailyCapacity rd ON r.RestaurantID = rd.RestaurantID
            WHERE rd.Date = @SelectedDate";

                        using (SqlCommand command = new SqlCommand(query, connection))
                        {
                            command.Parameters.AddWithValue("@SelectedDate", selectedDate);

                            using (SqlDataReader reader = command.ExecuteReader())
                            {
                                // Loop through all available restaurants and add to ComboBox
                                while (reader.Read())
                                {
                                    ComboboxItem item = new ComboboxItem
                                    {
                                        Text = reader["Name"].ToString(),  // Restaurant Name
                                        Value = Convert.ToInt32(reader["RestaurantID"]),  // Restaurant ID
                                        RemainingCapacity = Convert.ToInt32(reader["RemainingCapacity"])  // Remaining Capacity
                                    };
                                    Resturantnamecombo.Items.Add(item);  // Add the item to ComboBox

                                    // Append the restaurant name and remaining capacity to the label string
                                    restaurantInfo += $"{item.Text}: {item.RemainingCapacity} capacity available\n";
                                }
                            }
                        }
                    }

                    // Enable the ComboBox if we have any restaurants
                    Resturantnamecombo.Enabled = Resturantnamecombo.Items.Count > 0;

                    if (Resturantnamecombo.Items.Count == 0)
                    {
                        MessageBox.Show("No restaurants with sufficient capacity available for the selected date.", "Information", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    }
                    else
                    {
                        // Update the label with the restaurant info
                        RemainingCapacitylabel.Text = restaurantInfo;
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }

            else {


                // Clear existing items
                Resturantnamecombo.Items.Clear();

                // Variable to hold the restaurant list to show in the label
                string restaurantInfo = "";

                // Load data from the database
                DateTime selectedDate = reservationdateandtime.Value.Date;

                try
                {
                    using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                    {
                        connection.Open();
                        string query = @"
            SELECT r.RestaurantID, r.Name, rd.RemainingCapacity
            FROM Restaurant r
            INNER JOIN RestaurantDailyCapacity rd ON r.RestaurantID = rd.RestaurantID
            WHERE rd.Date = @SelectedDate";

                        using (SqlCommand command = new SqlCommand(query, connection))
                        {
                            command.Parameters.AddWithValue("@SelectedDate", selectedDate);

                            using (SqlDataReader reader = command.ExecuteReader())
                            {
                                // Loop through all available restaurants and add to ComboBox
                                while (reader.Read())
                                {
                                    ComboboxItem item = new ComboboxItem
                                    {
                                        Text = reader["Name"].ToString(),  // Restaurant Name
                                        Value = Convert.ToInt32(reader["RestaurantID"]),  // Restaurant ID
                                        RemainingCapacity = Convert.ToInt32(reader["RemainingCapacity"])  // Remaining Capacity
                                    };
                                    Resturantnamecombo.Items.Add(item);  // Add the item to ComboBox

                                    // Append the restaurant name and remaining capacity to the label string
                                    restaurantInfo += $"{item.Text}: {item.RemainingCapacity} capacity available\n";
                                }
                            }
                        }
                    }

                    // Enable the ComboBox if we have any restaurants
                    Resturantnamecombo.Enabled = Resturantnamecombo.Items.Count > 0;

                    if (Resturantnamecombo.Items.Count == 0)
                    {
                        MessageBox.Show("No restaurants with sufficient capacity available for the selected date.", "Information", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    }
                    else
                    {
                        // Update the label with the restaurant info
                        RemainingCapacitylabel.Text = restaurantInfo;
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }


        private int GetSelectedCustomerId()
        {
            // Logic to fetch the selected customer ID
            // This can be implemented by providing a way to select a customer in the form
            // Placeholder logic below:
            return 1; // Replace with actual customer selection logic
        }

        private void ClearReservationFields()
        {
            reservationdateandtime.Value = DateTime.Now;
            Resturantnamecombo.SelectedIndex = -1;
            capacitytxt.Clear();
        }






        private void PopulateMenuItems()
        {
            try
            {
                // Create a connection to the database
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    connection.Open();

                    // SQL query to get ONLY ACTIVE items from the Menu table
                    // We added 'WHERE IsActive = 1'
                    string query = "SELECT ItemName FROM Menu WHERE IsActive = 1";

                    using (SqlCommand command = new SqlCommand(query, connection))
                    {
                        // Execute the query and read the data
                        using (SqlDataReader reader = command.ExecuteReader())
                        {
                            // Clear any existing items in the ComboBox
                            itemmenucombo.Items.Clear();

                            // Add items to ComboBox from the database
                            while (reader.Read())
                            {
                                string itemName = reader.GetString(0);
                                itemmenucombo.Items.Add(itemName);
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error loading menu items: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }






        private void itemmenucombo_SelectedIndexChanged(object sender, EventArgs e)
        {
            // Handle selection change if necessary
            string selectedItem = itemmenucombo.SelectedItem.ToString();
            
        }


        public class Item
        {
            public string ItemName { get; set; }
            public int Quantity { get; set; }
            public decimal ItemPrice { get; set; }
            public decimal ItemTotalPrice { get; set; }
        }

        private List<Item> addedItems = new List<Item>();
        private decimal totalPrice = 0.0m;


        // Define a variable to store the total price


        private void additembtn_Click(object sender, EventArgs e)
        {


            string selectedItem = itemmenucombo.SelectedItem.ToString();
            if (int.TryParse(quantitytxt.Text, out int quantity) && quantity > 0)
            {
                try
                {
                    decimal itemPrice = GetItemPrice(selectedItem);
                    decimal itemTotalPrice = itemPrice * quantity;
                    totalPrice += itemTotalPrice;

                    Item newItem = new Item
                    {
                        ItemName = selectedItem,
                        Quantity = quantity,
                        ItemPrice = itemPrice,
                        ItemTotalPrice = itemTotalPrice
                    };
                    addedItems.Add(newItem);

                    AddItemToPanel(selectedItem, quantity, itemPrice, itemTotalPrice);
                    totalPriceLabel.Text = $"Total Price: {totalPrice}";
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error adding item: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
            else
            {
                MessageBox.Show("Please enter a valid quantity.", "Invalid Quantity", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }


        // Method to fetch the price of the selected item from the Menu table
        private decimal GetItemPrice(string itemName)
        {
            decimal itemPrice = 0;

            try
            {
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    connection.Open();

                    string query = "SELECT ItemPrice FROM Menu WHERE ItemName = @ItemName";
                    using (SqlCommand command = new SqlCommand(query, connection))
                    {
                        command.Parameters.AddWithValue("@ItemName", itemName);

                        // Execute the query and get the price
                        object result = command.ExecuteScalar();
                        if (result != null)
                        {
                            itemPrice = Convert.ToDecimal(result);
                        }
                        else
                        {
                            throw new Exception("Item not found.");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                throw new Exception("Error retrieving item price: " + ex.Message);
            }

            return itemPrice;
        }

        // Method to add the selected item to the panel
        private Label selectedItemLabel = null;  // To store the selected row

        private void AddItemToPanel(string itemName, int quantity, decimal itemPrice, decimal itemTotalPrice)
        {
            // Constants for padding, column widths, and row height
            int padding = 5;
            int columnWidthItemName = 100;  // Width for the item name column
            int columnWidthQuantity = 70;   // Width for the quantity column
            int columnWidthPrice = 100;      // Width for the price column
            int rowHeight = 40;             // Fixed height for each row

            // Add headers if this is the first row
            if (menuitemspanel.Controls.Count == 0)
            {
                AddHeaders(columnWidthItemName, columnWidthQuantity, columnWidthPrice, rowHeight, padding);
            }

            // Calculate the Y position for the new row
            int lastRowYPosition = menuitemspanel.Controls.Count > 3
                ? menuitemspanel.Controls[menuitemspanel.Controls.Count - 3].Location.Y + rowHeight
                : rowHeight;

            // Create and configure the labels for the new row
            Label itemNameLabel = new Label
            {
                Text = itemName,
                Width = columnWidthItemName,
                Height = rowHeight,
                Location = new Point(padding, lastRowYPosition),
                Cursor = Cursors.Hand // Indicate that the label is clickable
            };
            itemNameLabel.Click += new EventHandler(RowLabel_Click);  // Add click event for row selection

            Label quantityLabel = new Label
            {
                Text = quantity.ToString(),
                Width = columnWidthQuantity,
                Height = rowHeight,
                Location = new Point(itemNameLabel.Location.X + columnWidthItemName + padding, lastRowYPosition)
            };

            Label priceLabel = new Label
            {
                Text = $"{"   "+itemTotalPrice}",
                Width = columnWidthPrice,
                Height = rowHeight,
                Location = new Point(quantityLabel.Location.X + columnWidthQuantity + padding, lastRowYPosition),
                Tag = itemTotalPrice // Store raw price for calculations
            };

            // Add the labels to the panel
            menuitemspanel.Controls.Add(itemNameLabel);
            menuitemspanel.Controls.Add(quantityLabel);
            menuitemspanel.Controls.Add(priceLabel);

            // Adjust the scrollable area of the panel
            int totalHeight = ((menuitemspanel.Controls.Count / 3) + 1) * rowHeight;
            menuitemspanel.AutoScrollMinSize = new Size(menuitemspanel.Width, totalHeight);
            menuitemspanel.AutoScroll = true;
        }

        /// <summary>
        /// Adds static headers to the panel if they are not already present.
        /// </summary>
        private void AddHeaders(int columnWidthItemName, int columnWidthQuantity, int columnWidthPrice, int rowHeight, int padding)
        {
            Label itemHeaderLabel = new Label
            {
                Text = "ITEM",
                Width = columnWidthItemName,
                Height = rowHeight,
                Location = new Point(padding, 0),
                Font = new Font(FontFamily.GenericSansSerif, 10, FontStyle.Bold)
            };

            Label quantityHeaderLabel = new Label
            {
                Text = "PIECE",
                Width = columnWidthQuantity,
                Height = rowHeight,
                Location = new Point(itemHeaderLabel.Location.X + columnWidthItemName + padding, 0),
                Font = new Font(FontFamily.GenericSansSerif, 10, FontStyle.Bold)
            };

            Label priceHeaderLabel = new Label
            {
                Text = "PRICE",
                Width = columnWidthPrice,
                Height = rowHeight,
                Location = new Point(quantityHeaderLabel.Location.X + columnWidthQuantity + padding, 0),
                Font = new Font(FontFamily.GenericSansSerif, 10, FontStyle.Bold)
            };

            menuitemspanel.Controls.Add(itemHeaderLabel);
            menuitemspanel.Controls.Add(quantityHeaderLabel);
            menuitemspanel.Controls.Add(priceHeaderLabel);
        }

        // Event handler when a row is clicked
        private void RowLabel_Click(object sender, EventArgs e)
        {
            // Deselect previously selected row if any
            if (selectedItemLabel != null)
            {
                selectedItemLabel.BackColor = SystemColors.Control; // Reset background color
            }

            // Set the new selected row
            selectedItemLabel = (Label)sender;
            selectedItemLabel.BackColor = Color.LightBlue; // Highlight the selected row
        }

        // Delete button click handler


        // Adjust row positions if needed after deletion
        private void AdjustRowPositions()
        {
            int rowHeight = 40; // Height of each row
            int padding = 20; // Padding between columns
            int columnWidthItemName = 100;
            int columnWidthQuantity = 70;
            int columnWidthPrice = 100;

            // Start positioning after headers
            int yPosition = rowHeight;

            for (int i = 3; i < menuitemspanel.Controls.Count; i += 3)
            {
                var itemNameLabel = (Label)menuitemspanel.Controls[i];
                itemNameLabel.Location = new Point(padding, yPosition);

                var quantityLabel = (Label)menuitemspanel.Controls[i + 1];
                quantityLabel.Location = new Point(itemNameLabel.Location.X + columnWidthItemName + padding, yPosition);

                var priceLabel = (Label)menuitemspanel.Controls[i + 2];
                priceLabel.Location = new Point(quantityLabel.Location.X + columnWidthQuantity + padding, yPosition);

                yPosition += rowHeight;
            }

            // Update the minimum scrollable area
            int totalHeight = (menuitemspanel.Controls.Count / 3) * rowHeight + rowHeight;
            menuitemspanel.AutoScrollMinSize = new Size(menuitemspanel.Width, totalHeight);
        }

        private void UpdateTotalPrice(decimal change)
        {
            totalPrice += change;
            totalPriceLabel.Text = $"Total Price: {totalPrice}";
        }



        private async  void deletebtn_Click(object sender, EventArgs e)
        {

            await Task.Delay(300); // Wait for 300ms before processing
            if (selectedItemLabel != null)
            {
                int selectedIndex = menuitemspanel.Controls.IndexOf(selectedItemLabel);

                if (selectedIndex < 3 || selectedIndex + 2 >= menuitemspanel.Controls.Count)
                {
                    MessageBox.Show("Invalid selection. Please select a valid row.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }

                // Get the labels for the selected row
                var itemNameLabel = selectedItemLabel;
                var quantityLabel = (Label)menuitemspanel.Controls[selectedIndex + 1];
                var priceLabel = (Label)menuitemspanel.Controls[selectedIndex + 2];

                // Retrieve the raw price from the Tag property
                if (priceLabel.Tag is decimal itemTotalPrice)
                {
                    totalPrice -= itemTotalPrice;
                    totalPrice = Math.Max(totalPrice, 0); // Ensure it doesn't go negative
                    totalPriceLabel.Text = $"Total Price: {totalPrice}";
                }
                else
                {
                    MessageBox.Show("Price information is missing or invalid.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }

                // Remove labels from the panel
                menuitemspanel.Controls.Remove(itemNameLabel);
                menuitemspanel.Controls.Remove(quantityLabel);
                menuitemspanel.Controls.Remove(priceLabel);

                // Deselect the row
                selectedItemLabel = null;

                // Adjust positions of remaining rows
                AdjustRowPositions();

                // Now delete from the addedItems list (the correct name for your array/list)
                string itemName = itemNameLabel.Text;
                int itemIndexToDelete = -1;

                // Assuming addedItems is a List<Item> (from your provided code)
                for (int i = 0; i < addedItems.Count; i++)
                {
                    if (addedItems[i].ItemName == itemName)
                    {
                        itemIndexToDelete = i;
                        break;
                    }
                }

                if (itemIndexToDelete >= 0)
                {
                    // Remove the item from the list
                    addedItems.RemoveAt(itemIndexToDelete);
                    Debug.WriteLine($"Item '{itemName}' removed from addedItems list.");
                }
                else
                {
                    MessageBox.Show($"Item '{itemName}' not found in addedItems list.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
            else
            {
                MessageBox.Show("Please select a row to delete.", "Warning", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }



        private void printnpaybtn_Click(object sender, EventArgs e)
        {
            // Logic for printing or paying (this can be implemented later)
            MessageBox.Show("Print and Pay functionality goes here.", "Print and Pay", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }


        private void menuitemspanel_Paint(object sender, PaintEventArgs e)
        {

        }

        private void Home_Load(object sender, EventArgs e)
        {
           ;



        clockTimer = new System.Threading.Timer(UpdateDateTime, null, 0, 1000); // 1 second interval

            quantitytxt.Text = "1";
            ConfigureNameAutoComplete();


            cashiernamelabel.Text = _username;

            Cashradiobtn.Checked = true;    




        }


       

        private void UpdateDateTime(object state)
        {
            try
            {
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    connection.Open();

                    // Query to get the current date and time from the database
                    string query = "SELECT GETDATE()";

                    using (SqlCommand command = new SqlCommand(query, connection))
                    {
                        try
                        {
                            object result = command.ExecuteScalar();
                            if (result != null)
                            {
                                // Safely convert the result
                                DateTime dateTimeNow = Convert.ToDateTime(result);
                                string formattedDateTime = dateTimeNow.ToString("yyyy-MM-dd HH:mm:ss");

                                // Update the TextBox on the UI thread
                                if (this.InvokeRequired)
                                {
                                    this.Invoke(new Action(() =>
                                    {
                                        DatenTimetxt.Text = formattedDateTime;
                                    }));
                                }
                                else
                                {
                                    DatenTimetxt.Text = formattedDateTime;
                                }
                            }
                            else
                            {
                                // Handle null result from the database query
                                this.Invoke(new Action(() =>
                                {
                                    DatenTimetxt.Text = "Error: Unable to fetch date and time";
                                }));
                            }
                        }
                        catch (Exception sqlEx)
                        {
                            // Handle SQL execution errors
                            this.Invoke(new Action(() =>
                            {
                                DatenTimetxt.Text = $"SQL Error: {sqlEx.Message}";
                            }));
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                // Handle connection errors
                this.Invoke(new Action(() =>
                {
                    DatenTimetxt.Text = $"Error: {ex.Message}";
                }));
            }
        }




        private void Home_FormClosing(object sender, FormClosingEventArgs e)
        {
            clockTimer?.Dispose();
        }



        private int GetMenuItemId(string itemName)
        {
            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                string query = "SELECT MenuItemID FROM Menu WHERE ItemName = @ItemName";
                SqlCommand cmd = new SqlCommand(query, conn);
                cmd.Parameters.AddWithValue("@ItemName", itemName);

                conn.Open();
                object result = cmd.ExecuteScalar();
                conn.Close();

                if (result != null && int.TryParse(result.ToString(), out int menuItemId))
                {
                    return menuItemId;
                }
                else
                {
                    throw new Exception($"Menu item '{itemName}' not found in the database.");
                }
            }
        }







       




        private void InsertPayment(int customerId, int reservationId, decimal totalAmount, decimal paidAmount)
        {
            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                string query = @"
            INSERT INTO Payments (CustomerID, ReservationID, TotalAmount, PaidAmount)
            VALUES (@CustomerID, @ReservationID, @TotalAmount, @PaidAmount)";
                SqlCommand cmd = new SqlCommand(query, conn);
                cmd.Parameters.AddWithValue("@CustomerID", customerId);
                cmd.Parameters.AddWithValue("@ReservationID", reservationId);
                cmd.Parameters.AddWithValue("@TotalAmount", totalAmount);
                cmd.Parameters.AddWithValue("@PaidAmount", paidAmount);

                conn.Open();
                cmd.ExecuteNonQuery();
                conn.Close();
            }
        }







        private int GetCustomerId()
        {
            // Get the customer name and phone number from the textboxes
            string customerName = nametxt.Text;
            string phoneNumber = Phonenumbertxt.Text;

            // Initialize the connection string (adjust this to your database configuration)
            string connectionString = DatabaseConfig.connectionString;

            // SQL query to get CustomerID based on the provided name and phone number
            string query = "SELECT customerid FROM Customer WHERE Name = @Name AND PhoneNumber = @PhoneNumber";

            using (SqlConnection connection = new SqlConnection(connectionString))
            {
                try
                {
                    // Open the database connection
                    connection.Open();

                    using (SqlCommand command = new SqlCommand(query, connection))
                    {
                        // Add parameters to the SQL query to avoid SQL injection
                        command.Parameters.AddWithValue("@Name", customerName);
                        command.Parameters.AddWithValue("@PhoneNumber", phoneNumber);

                        // Execute the query and get the result
                        object result = command.ExecuteScalar();

                        // Check if a result is returned
                        if (result != null)
                        {
                            // Return the CustomerID (assumes ID is an int)
                            return Convert.ToInt32(result);
                        }
                        else
                        {
                            MessageBox.Show("Customer not found.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                            return -1; // Or handle as appropriate
                        }
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return -1; // Or handle as appropriate
                }
            }
        }

        private void ClearMenuItems()
        {
            // Clear the ComboBox items or reset its selected value
            itemmenucombo.Text = ""; // Reset selected item
       
            // Reset the quantity text box or numeric control
            quantitytxt.Text = "1"; // If it's a TextBox
            paidamount.Text = "";
            totalPrice = 0;
            totalPriceLabel.Text = "";
            // quantitytxt.Value = 1; // If it's a NumericUpDown
            menuitemspanel.Controls.Clear();

            // Clear the addedItems array
            addedItems.Clear(); // Assuming addedItems is a List or similar collection type
            // Clear all child controls in the menu items panel
          
        }




        private async void printnpaybtn_Click_1(object sender, EventArgs e)
        {
            // Prevent multiple clicks
            printnpaybtn.Enabled = false;
            await Task.Delay(2000); // Wait for 300ms before processing

            try
            {
                string totalPriceText = totalPriceLabel.Text.Replace("Total Price:", "").Replace("£", "").Replace("$", "").Trim();
                if (!decimal.TryParse(totalPriceText, out decimal totalAmount))
                {
                    MessageBox.Show($"Failed to parse Total Price '{totalPriceLabel.Text}'. Ensure the format is correct.", "Invalid Input", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }

                if (!decimal.TryParse(paidamount.Text, out decimal paidAmount))
                {
                    MessageBox.Show($"Failed to parse Paid Amount '{paidamount.Text}'. Ensure the input is correct.", "Invalid Input", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }

                if (!int.TryParse(reservationidtxt.Text, out int reservationId))
                {
                    MessageBox.Show($"Failed to parse Reservation ID '{reservationidtxt.Text}'. Ensure the input is a valid number.", "Invalid Input", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }

                // Fetch capacity
                string capacity = GetCapacityFromDatabase(reservationId);
                if (string.IsNullOrEmpty(capacity))
                {
                    MessageBox.Show("Failed to retrieve capacity for this reservation.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    connection.Open();

                    // Insert or update payment
                    string paymentQuery = @"
            IF EXISTS (SELECT 1 FROM Payments WHERE CustomerID = @CustomerID AND ReservationID = @ReservationID)
            BEGIN
                UPDATE Payments
                SET TotalAmount = TotalAmount + @TotalAmount, 
                    PaidAmount = PaidAmount + @PaidAmount
                WHERE CustomerID = @CustomerID AND ReservationID = @ReservationID
            END
            ELSE
            BEGIN
                INSERT INTO Payments (CustomerID, ReservationID, TotalAmount, PaidAmount)
                VALUES (@CustomerID, @ReservationID, @TotalAmount, @PaidAmount)
            END";

                    using (SqlCommand paymentCommand = new SqlCommand(paymentQuery, connection))
                    {
                        paymentCommand.Parameters.AddWithValue("@CustomerID", GetCustomerId());
                        paymentCommand.Parameters.AddWithValue("@ReservationID", reservationId);
                        paymentCommand.Parameters.AddWithValue("@TotalAmount", totalAmount);
                        paymentCommand.Parameters.AddWithValue("@PaidAmount", paidAmount);
                        paymentCommand.ExecuteNonQuery();
                    }

                    // Update Notes in Reservation
                    string updateNotesQuery = "UPDATE Reservations SET Notes = @Notes WHERE ReservationID = @ReservationID";
                    using (SqlCommand updateNotesCommand = new SqlCommand(updateNotesQuery, connection))
                    {
                        updateNotesCommand.Parameters.AddWithValue("@Notes", notestxt.Text.Trim());
                        updateNotesCommand.Parameters.AddWithValue("@ReservationID", reservationId);
                        updateNotesCommand.ExecuteNonQuery();
                    }

                    // Insert into DailyPayments
                    string dailyInsertQuery = "INSERT INTO DailyPayments (CustomerID, ReservationID, PaidAmount, PaymentDate, CashierName , Paymentmethod) VALUES (@CustomerID, @ReservationID, @PaidAmount, GETDATE(), @CashierName , @PaymentMethod)";
                    using (SqlCommand dailyInsertCommand = new SqlCommand(dailyInsertQuery, connection))
                    {
                        dailyInsertCommand.Parameters.AddWithValue("@PaidAmount", paidAmount);
                        dailyInsertCommand.Parameters.AddWithValue("@ReservationID", reservationId);
                        dailyInsertCommand.Parameters.AddWithValue("@CustomerID", GetCustomerId());
                        dailyInsertCommand.Parameters.AddWithValue("@CashierName", _username);
                        dailyInsertCommand.Parameters.AddWithValue("@Paymentmethod", paymentMethod);
                        dailyInsertCommand.ExecuteNonQuery();
                    }

                    // Insert into OrderDetails
                    foreach (var item in addedItems)
                    {
                        int menuItemId = GetMenuItemIdByName(item.ItemName);
                        decimal subtotal = item.ItemPrice * item.Quantity;

                        string orderDetailsQuery = "INSERT INTO OrderDetails (ReservationID, MenuItemID, Quantity, ItemPrice, CashierName) " +
                                                    "VALUES (@ReservationID, @MenuItemID, @Quantity, @ItemPrice, @CashierName)";
                        using (SqlCommand orderDetailsCommand = new SqlCommand(orderDetailsQuery, connection))
                        {
                            orderDetailsCommand.Parameters.AddWithValue("@ReservationID", reservationId);
                            orderDetailsCommand.Parameters.AddWithValue("@MenuItemID", menuItemId);
                            orderDetailsCommand.Parameters.AddWithValue("@Quantity", item.Quantity);
                            orderDetailsCommand.Parameters.AddWithValue("@ItemPrice", item.ItemPrice);
                            orderDetailsCommand.Parameters.AddWithValue("@CashierName", _username);
                            orderDetailsCommand.ExecuteNonQuery();
                        }
                    }
                    

                    // Insert into UserLog
                    string logQuery = "INSERT INTO UserLog (CashierName, Action, DateAndTime) VALUES (@CashierName, @Action, GETDATE())";
                    using (SqlCommand logCommand = new SqlCommand(logQuery, connection))
                    {
                        string logDetails = $"Processed Reservation ID: {reservationId}, Paid Amount: {paidAmount}, Total Amount: {totalAmount} , New Reservation";
                        logCommand.Parameters.AddWithValue("@CashierName", _username);
                        logCommand.Parameters.AddWithValue("@Action", logDetails);
                        logCommand.ExecuteNonQuery();
                    }


                   

                    // Print receipt with the fetched capacity
                    PrintReceipt(reservationId, totalAmount, paidAmount, _username, capacity);
                    
                    PrintCopyReceipt(reservationId, totalAmount, paidAmount, _username, capacity);

                    ClearMenuItems();
                    MessageBox.Show("Order details and payment saved successfully!", "Success", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    
                    ResetForm();
                    Home home = new Home(_username);
                    this.Hide();
                    home.ShowDialog();
                    this.Close();
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                // Re-enable button after operation
                printnpaybtn.Enabled = true;
            }
        }


        private string GetCapacityFromDatabase(int reservationId)
        {
            string capacity = string.Empty;
            string connectionString = DatabaseConfig.connectionString; // Replace with your actual connection string

            // Query to fetch capacity from reservations table
            string query = "SELECT NumberOfGuests FROM reservations WHERE reservationid = @reservationId";

            using (SqlConnection conn = new SqlConnection(connectionString))
            {
                try
                {
                    conn.Open();
                    using (SqlCommand cmd = new SqlCommand(query, conn))
                    {
                        cmd.Parameters.AddWithValue("@reservationId", reservationId);
                        var result = cmd.ExecuteScalar();
                        capacity = result?.ToString(); // If result is null, capacity remains empty
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error fetching capacity: {ex.Message}", "Database Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }

            return capacity;
        }




        // Method to handle printing
        private void PrintReceipt(int reservationId, decimal totalAmount, decimal paidAmount, string cashierName, string numberOfGuests)
        {
            DateTime reservationDateAndTime = reservationdateandtime.Value;
            string formattedReservationDateAndTime = reservationDateAndTime.ToString("dd/MM/yyyy");

            // Retrieve the restaurant name from the database based on reservationId
            string restaurantName = GetRestaurantNameByReservationId(reservationId);


            string notes = string.Empty;

            // Fetch notes from the Reservations table
            using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
            {
                connection.Open();
                string notesQuery = "SELECT Notes FROM Reservations WHERE ReservationID = @ReservationID";
                using (SqlCommand notesCommand = new SqlCommand(notesQuery, connection))
                {
                    notesCommand.Parameters.AddWithValue("@ReservationID", reservationId);
                    var result = notesCommand.ExecuteScalar();
                    if (result != null)
                    {
                        notes = result.ToString();
                    }
                }
            }

            PrintDocument printDocument = new PrintDocument();
            printDocument.PrintPage += (sender, e) =>
            {
                float yPosition = 10; // Starting Y position
                float rightMargin = e.PageBounds.Width - 10; // Right margin
                float leftMargin = 10; // Left margin
                float header = 50;
                float lineHeight = 25; // Line height for spacing
                Font font = new Font("Arial", 10);
                Font boldFont = new Font("Arial", 10, FontStyle.Bold);
               
                Font titleFont = new Font("Arial", 12, FontStyle.Bold);
                StringFormat rtlFormat = new StringFormat { Alignment = StringAlignment.Far }; // Right-to-left alignment
                StringFormat leftFormat = new StringFormat { Alignment = StringAlignment.Near }; // Left alignment
                StringFormat centerFormat = new StringFormat { Alignment = StringAlignment.Center }; // Center alignment

                // Draw the company logo
                string logoPath = Path.Combine(Application.StartupPath, "logo.png"); // Replace with the actual path to the logo
                if (System.IO.File.Exists(logoPath))
                {
                    Image logo = Image.FromFile(logoPath);
                    e.Graphics.DrawImage(logo, (e.PageBounds.Width - 100) / 2, yPosition, 100, 100); // Center the logo
                    yPosition += 110; // Adjust for logo height
                }

                // Draw the company name in the center
                string companyName = "Royal Resort";
                e.Graphics.DrawString(companyName, titleFont, Brushes.Black, e.PageBounds.Width / 2, yPosition, centerFormat);
                yPosition += header;

                // Add the date and time
                e.Graphics.DrawString($"تاريخ: {DateTime.Now:dd/MM/yyyy HH:mm:ss}", font, Brushes.Black, rightMargin, yPosition, rtlFormat);
                yPosition += lineHeight;

                // Add reservation ID on the right and reservation date on the left (same line)
                e.Graphics.DrawString($"رقم الحجز: {reservationId}", boldFont, Brushes.Black, rightMargin, yPosition, rtlFormat); // Right aligned
                e.Graphics.DrawString($"تاريخ الحجز: {formattedReservationDateAndTime}", boldFont, Brushes.Black, leftMargin, yPosition, leftFormat); // Left aligned
                yPosition += lineHeight;


                // Set the maximum number of characters allowed
                int maxNameLength = 14;
                int maxCashierNameLength = 13; // Ensure both are within limits

                // Truncate the name if it exceeds the max length
                string truncatedName = nametxt.Text.Length > maxNameLength
                    ? nametxt.Text.Substring(0, maxNameLength)
                    : nametxt.Text;

                string truncatedCashierName = cashierName.Length > maxCashierNameLength
                    ? cashierName.Substring(0, maxCashierNameLength)
                    : cashierName;

                // Draw the text with proper alignment
                e.Graphics.DrawString($"حجز باسم: {truncatedName}", boldFont, Brushes.Black, rightMargin, yPosition, rtlFormat); // Right aligned
                e.Graphics.DrawString($"القائم بالحجز: {truncatedCashierName}", boldFont, Brushes.Black, leftMargin, yPosition, leftFormat); // Left aligned
                yPosition += lineHeight; // Move to next line


                string resturantname = $" مطعم:  {restaurantName}";
                // Add the restaurant name under the customer name and number of guests
                e.Graphics.DrawString(resturantname, boldFont, Brushes.Black, leftMargin, yPosition, leftFormat);
                string numberOfGuestsText = $"عدد اشخاص: {numberOfGuests}";
                e.Graphics.DrawString(numberOfGuestsText, boldFont, Brushes.Black, rightMargin, yPosition, rtlFormat);
                yPosition += lineHeight;

                // Draw a separator
                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                yPosition += 10;

                // Add the order details
                e.Graphics.DrawString(": تفاصيل الاوردر", titleFont, Brushes.Black, rightMargin, yPosition, rtlFormat);
                yPosition += lineHeight;

                // Define column widths (adjust as needed)
                float columnWidthItem = 150; // Width for the item name column
                float columnWidthQuantity = 70; // Width for the quantity column
                float columnWidthPrice = 70; // Width for the price column
                float columnWidthSubtotal = 80; // Width for the subtotal column

                // Draw table headers (RTL alignment)
                string headerItem = "العنصر";
                string headerQuantity = "الكمية";
             
                string headerSubtotal = "الإجمالي";

                // Calculate starting X positions for each column (RTL)
                float xPositionItem = rightMargin;
                float xPositionQuantity = xPositionItem - columnWidthItem;
               
                float xPositionSubtotal = xPositionQuantity - columnWidthPrice;

                // Draw headers
                e.Graphics.DrawString(headerItem, boldFont, Brushes.Black, xPositionItem, yPosition, rtlFormat);
                e.Graphics.DrawString(headerQuantity, boldFont, Brushes.Black, xPositionQuantity, yPosition, rtlFormat);
               
                e.Graphics.DrawString(headerSubtotal, boldFont, Brushes.Black, xPositionSubtotal, yPosition, rtlFormat);
                yPosition += lineHeight;

                // Draw a separator line under headers
                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                yPosition += 10;

                // Dictionary to store the total quantities for each added item
                Dictionary<string, (decimal ItemPrice, int TotalQuantity)> addedItemTotals = new Dictionary<string, (decimal, int)>();

                // Loop through added items and sum the quantities for the same item
                foreach (var item in addedItems)
                {
                    string itemName = item.ItemName;
                    decimal itemPrice = item.ItemPrice;
                    int quantity = item.Quantity;

                    // Check if the item already exists in the dictionary, if so, update the quantity
                    if (addedItemTotals.ContainsKey(itemName))
                    {
                        addedItemTotals[itemName] = (itemPrice, addedItemTotals[itemName].TotalQuantity + quantity);
                    }
                    else
                    {
                        addedItemTotals.Add(itemName, (itemPrice, quantity));
                    }
                }

                // Now print each added item and its total quantity
                foreach (var item in addedItemTotals)
                {
                    string itemName = item.Key;
                    decimal itemPrice = item.Value.ItemPrice;
                    int totalQuantity = item.Value.TotalQuantity;
                    decimal subtotal = itemPrice * totalQuantity;

                    // Draw item name (right-aligned under "العنصر")
                    e.Graphics.DrawString(itemName, font, Brushes.Black, xPositionItem, yPosition, rtlFormat);

                    // Draw quantity (right-aligned under "الكمية")
                    e.Graphics.DrawString(totalQuantity.ToString(), font, Brushes.Black, xPositionQuantity, yPosition, rtlFormat);

                  

                    // Draw subtotal (right-aligned under "الإجمالي")
                    e.Graphics.DrawString(subtotal.ToString("0.##"), font, Brushes.Black, xPositionSubtotal, yPosition, rtlFormat);

                    // Move to the next line
                    yPosition += lineHeight;
                }

              

                if (!string.IsNullOrEmpty(notes))
                {
                    // Draw another separator
                    e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                    yPosition += 10;

                    e.Graphics.DrawString(":ملحوظات", titleFont, Brushes.Black, rightMargin, yPosition, rtlFormat);
                    yPosition += lineHeight;

                    // Calculate the size of the notes string
                    float availableWidth = e.PageBounds.Width - leftMargin - rightMargin;
                    SizeF notesSize = e.Graphics.MeasureString(notes, font, (int)availableWidth);

                    // Define a rectangle for multi-line text rendering
                    RectangleF notesRect = new RectangleF(rightMargin, yPosition, availableWidth, notesSize.Height);

                    // Render the notes text inside the rectangle
                    e.Graphics.DrawString(notes, font, Brushes.Black, notesRect, rtlFormat);

                    // Update yPosition to account for the height of the rendered text
                    yPosition += (int)notesSize.Height;
                }

               

                // Draw another separator
                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                yPosition += 10;


                e.Graphics.DrawString($"اجمالي المبلغ: {totalAmount:0.##}", boldFont, Brushes.Black, leftMargin, yPosition);
                yPosition += lineHeight;


                    // Display paid amount and remaining total on the same line
                    e.Graphics.DrawString($"المبلغ المدفوع: {paidAmount:N2}",
                        boldFont, Brushes.Black, leftMargin, yPosition);
                    yPosition += lineHeight;


                    e.Graphics.DrawString($"اجمالي المتبقى: {totalAmount - paidAmount:N2}", boldFont, Brushes.Black, leftMargin, yPosition);
                    yPosition += lineHeight;



                    // Display paid amount and remaining total on the same line
                    e.Graphics.DrawString($"الاسعار شامله قيمة الضريبه المضافه",
                 boldFont, Brushes.Black, e.PageBounds.Width / 2, yPosition, centerFormat);
                yPosition += lineHeight;


                // Draw another separator
                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                yPosition += 10;

                // Add total amount (without currency symbol)


                // Add the footer message
                string footerMessage = "شكرا على اختيارك دار الضيافة";
                e.Graphics.DrawString(footerMessage, boldFont, Brushes.Black, e.PageBounds.Width / 2, yPosition, centerFormat);
                yPosition += 20;

               

                // Ensure the footer does not overflow the page height
                if (yPosition + lineHeight > e.PageBounds.Height)
                {
                    MessageBox.Show("The receipt content exceeds the page height. Please adjust margins or content.", "Print Warning", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
            };

            try
            {
                printDocument.Print();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"An error occurred while printing: {ex.Message}", "Print Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }







        private void PrintCopyReceipt(int reservationId, decimal totalAmount, decimal paidAmount, string cashierName, string numberOfGuests)
        {
            DateTime reservationDateAndTime = reservationdateandtime.Value;
            string formattedReservationDateAndTime = reservationDateAndTime.ToString("dd/MM/yyyy");

            // Retrieve the restaurant name from the database based on reservationId
            string restaurantName = GetRestaurantNameByReservationId(reservationId);


            string notes = string.Empty;

            // Fetch notes from the Reservations table
            using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
            {
                connection.Open();
                string notesQuery = "SELECT Notes FROM Reservations WHERE ReservationID = @ReservationID";
                using (SqlCommand notesCommand = new SqlCommand(notesQuery, connection))
                {
                    notesCommand.Parameters.AddWithValue("@ReservationID", reservationId);
                    var result = notesCommand.ExecuteScalar();
                    if (result != null)
                    {
                        notes = result.ToString();
                    }
                }
            }

            PrintDocument printDocument = new PrintDocument();
            printDocument.PrintPage += (sender, e) =>
            {
                float yPosition = 10; // Starting Y position
                float rightMargin = e.PageBounds.Width - 10; // Right margin
                float leftMargin = 10; // Left margin
                float header = 50;
                float lineHeight = 25; // Line height for spacing
                Font font = new Font("Arial", 10);
                Font boldFont = new Font("Arial", 10, FontStyle.Bold);

                Font titleFont = new Font("Arial", 12, FontStyle.Bold);
                StringFormat rtlFormat = new StringFormat { Alignment = StringAlignment.Far }; // Right-to-left alignment
                StringFormat leftFormat = new StringFormat { Alignment = StringAlignment.Near }; // Left alignment
                StringFormat centerFormat = new StringFormat { Alignment = StringAlignment.Center }; // Center alignment

                // Draw the company logo


                // Draw the receipt type
                e.Graphics.DrawString("Copy", new Font("Arial", 16, FontStyle.Bold), Brushes.Black, e.PageBounds.Width / 2, 5, centerFormat);
                yPosition += 40; // Adjust for logo height


                string logoPath = Path.Combine(Application.StartupPath, "logo.png"); // Replace with the actual path to the logo
                if (System.IO.File.Exists(logoPath))
                {
                    Image logo = Image.FromFile(logoPath);
                    e.Graphics.DrawImage(logo, (e.PageBounds.Width - 100) / 2, yPosition, 100, 100); // Center the logo
                    yPosition += 110; // Adjust for logo height
                }

                // Draw the company name in the center
                string companyName = "Royal Resort";
                e.Graphics.DrawString(companyName, titleFont, Brushes.Black, e.PageBounds.Width / 2, yPosition, centerFormat);
                yPosition += header;

                // Add the date and time
                e.Graphics.DrawString($"تاريخ: {DateTime.Now:dd/MM/yyyy HH:mm:ss}", font, Brushes.Black, rightMargin, yPosition, rtlFormat);
                yPosition += lineHeight;

                // Add reservation ID on the right and reservation date on the left (same line)
                e.Graphics.DrawString($"رقم الحجز: {reservationId}", boldFont, Brushes.Black, rightMargin, yPosition, rtlFormat); // Right aligned
                e.Graphics.DrawString($"تاريخ الحجز: {formattedReservationDateAndTime}", boldFont, Brushes.Black, leftMargin, yPosition, leftFormat); // Left aligned
                yPosition += lineHeight;


                // Set the maximum number of characters allowed
                int maxNameLength = 14;
                int maxCashierNameLength = 13; // Ensure both are within limits

                // Truncate the name if it exceeds the max length
                string truncatedName = nametxt.Text.Length > maxNameLength
                    ? nametxt.Text.Substring(0, maxNameLength)
                    : nametxt.Text;

                string truncatedCashierName = cashierName.Length > maxCashierNameLength
                    ? cashierName.Substring(0, maxCashierNameLength)
                    : cashierName;

                // Draw the text with proper alignment
                e.Graphics.DrawString($"حجز باسم: {truncatedName}", boldFont, Brushes.Black, rightMargin, yPosition, rtlFormat); // Right aligned
                e.Graphics.DrawString($"القائم بالحجز: {truncatedCashierName}", boldFont, Brushes.Black, leftMargin, yPosition, leftFormat); // Left aligned
                yPosition += lineHeight; // Move to next line


                string resturantname = $" مطعم:  {restaurantName}";
                // Add the restaurant name under the customer name and number of guests
                e.Graphics.DrawString(resturantname, boldFont, Brushes.Black, leftMargin, yPosition, leftFormat);
                string numberOfGuestsText = $"عدد اشخاص: {numberOfGuests}";
                e.Graphics.DrawString(numberOfGuestsText, boldFont, Brushes.Black, rightMargin, yPosition, rtlFormat);
                yPosition += lineHeight;

                // Draw a separator
                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                yPosition += 10;

             // Add the order details
                e.Graphics.DrawString(": تفاصيل الاوردر", titleFont, Brushes.Black, rightMargin, yPosition, rtlFormat);
                yPosition += lineHeight;

                // Define column widths (adjust as needed)
                float columnWidthItem = 150; // Width for the item name column
                float columnWidthQuantity = 70; // Width for the quantity column
                float columnWidthPrice = 70; // Width for the price column
                float columnWidthSubtotal = 80; // Width for the subtotal column

                // Draw table headers (RTL alignment)
                string headerItem = "العنصر";
                string headerQuantity = "الكمية";
                string headerPrice = "السعر";
                string headerSubtotal = "الإجمالي";

                // Calculate starting X positions for each column (RTL)
                float xPositionItem = rightMargin;
                float xPositionQuantity = xPositionItem - columnWidthItem;
              
                float xPositionSubtotal = xPositionQuantity - columnWidthPrice;

                // Draw headers
                e.Graphics.DrawString(headerItem, boldFont, Brushes.Black, xPositionItem, yPosition, rtlFormat);
                e.Graphics.DrawString(headerQuantity, boldFont, Brushes.Black, xPositionQuantity, yPosition, rtlFormat);
             
                e.Graphics.DrawString(headerSubtotal, boldFont, Brushes.Black, xPositionSubtotal, yPosition, rtlFormat);
                yPosition += lineHeight;

                // Draw a separator line under headers
                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                yPosition += 10;

                // Dictionary to store the total quantities for each added item
                Dictionary<string, (decimal ItemPrice, int TotalQuantity)> addedItemTotals = new Dictionary<string, (decimal, int)>();

                // Loop through added items and sum the quantities for the same item
                foreach (var item in addedItems)
                {
                    string itemName = item.ItemName;
                    decimal itemPrice = item.ItemPrice;
                    int quantity = item.Quantity;

                    // Check if the item already exists in the dictionary, if so, update the quantity
                    if (addedItemTotals.ContainsKey(itemName))
                    {
                        addedItemTotals[itemName] = (itemPrice, addedItemTotals[itemName].TotalQuantity + quantity);
                    }
                    else
                    {
                        addedItemTotals.Add(itemName, (itemPrice, quantity));
                    }
                }

                // Now print each added item and its total quantity
                foreach (var item in addedItemTotals)
                {
                    string itemName = item.Key;
                    decimal itemPrice = item.Value.ItemPrice;
                    int totalQuantity = item.Value.TotalQuantity;
                    decimal subtotal = itemPrice * totalQuantity;

                    // Draw item name (right-aligned under "العنصر")
                    e.Graphics.DrawString(itemName, font, Brushes.Black, xPositionItem, yPosition, rtlFormat);

                    // Draw quantity (right-aligned under "الكمية")
                    e.Graphics.DrawString(totalQuantity.ToString(), font, Brushes.Black, xPositionQuantity, yPosition, rtlFormat);

                  
                    // Draw subtotal (right-aligned under "الإجمالي")
                    e.Graphics.DrawString(subtotal.ToString("0.##"), font, Brushes.Black, xPositionSubtotal, yPosition, rtlFormat);

                    // Move to the next line
                    yPosition += lineHeight;
                }



                if (!string.IsNullOrEmpty(notes))
                {
                    // Draw another separator
                    e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                    yPosition += 10;

                    e.Graphics.DrawString(":ملحوظات", titleFont, Brushes.Black, rightMargin, yPosition, rtlFormat);
                    yPosition += lineHeight;

                    // Calculate the size of the notes string
                    float availableWidth = e.PageBounds.Width - leftMargin - rightMargin;
                    SizeF notesSize = e.Graphics.MeasureString(notes, font, (int)availableWidth);

                    // Define a rectangle for multi-line text rendering
                    RectangleF notesRect = new RectangleF(rightMargin, yPosition, availableWidth, notesSize.Height);

                    // Render the notes text inside the rectangle
                    e.Graphics.DrawString(notes, font, Brushes.Black, notesRect, rtlFormat);

                    // Update yPosition to account for the height of the rendered text
                    yPosition += (int)notesSize.Height;
                }

                // Draw another separator
                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                yPosition += 10;

                ClearMenuItems();


                e.Graphics.DrawString($"اجمالي المبلغ: {totalAmount:0.##}", boldFont, Brushes.Black, leftMargin, yPosition);
                yPosition += lineHeight;


                // Display paid amount and remaining total on the same line
                e.Graphics.DrawString($"المبلغ المدفوع: {paidAmount:N2}",
                    boldFont, Brushes.Black, leftMargin, yPosition);
                yPosition += lineHeight;


                e.Graphics.DrawString($"اجمالي المتبقى: {totalAmount - paidAmount:N2}", boldFont, Brushes.Black, leftMargin, yPosition);
                yPosition += lineHeight;



                // Display paid amount and remaining total on the same line
                e.Graphics.DrawString($"الاسعار شامله قيمة الضريبه المضافه",
             boldFont, Brushes.Black, e.PageBounds.Width / 2, yPosition, centerFormat);
                yPosition += lineHeight;


                // Draw another separator
                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, e.PageBounds.Width - leftMargin, yPosition);
                yPosition += 10;

                // Add total amount (without currency symbol)


                // Add the footer message
                string footerMessage = "شكرا على اختيارك دار الضيافة";
                e.Graphics.DrawString(footerMessage, boldFont, Brushes.Black, e.PageBounds.Width / 2, yPosition, centerFormat);
                yPosition += 20;



                // Ensure the footer does not overflow the page height
                if (yPosition + lineHeight > e.PageBounds.Height)
                {
                    MessageBox.Show("The receipt content exceeds the page height. Please adjust margins or content.", "Print Warning", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
            };

            try
            {
                printDocument.Print();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"An error occurred while printing: {ex.Message}", "Print Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }




        // Method to fetch the restaurant name based on reservationId
        private string GetRestaurantNameByReservationId(int reservationId)
        {
            string restaurantName = string.Empty;
            // Replace with actual database logic to fetch the restaurant name
            using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
            {
                connection.Open();
                string query = "SELECT Name FROM Restaurant WHERE RestaurantID = (SELECT RestaurantId FROM Reservations WHERE reservationid = @reservationId)";
                using (SqlCommand command = new SqlCommand(query, connection))
                {
                    command.Parameters.AddWithValue("@reservationId", reservationId);
                    restaurantName = command.ExecuteScalar()?.ToString() ?? "Restaurant Name Not Found";
                }
            }
            return restaurantName;
        }





        private int GetMenuItemIdByName(string itemName)
        {
            int menuItemId = -1;
            string query = "SELECT MenuItemID FROM Menu WHERE ItemName = @ItemName";
            using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
            {
                connection.Open();
                using (SqlCommand command = new SqlCommand(query, connection))
                {
                    command.Parameters.AddWithValue("@ItemName", itemName);
                    object result = command.ExecuteScalar();
                    if (result != null)
                    {
                        menuItemId = Convert.ToInt32(result);
                    }
                }
            }
            return menuItemId;
        }


        private void InsertOrderDetails(int reservationId, int menuItemId, int quantity, decimal itemPrice, decimal subtotal)
        {
            Debug.WriteLine($"Inserting order details: ReservationID={reservationId}, MenuItemID={menuItemId}, Quantity={quantity}, ItemPrice={itemPrice}, Subtotal={subtotal}");

            try
            {
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    connection.Open();
                    Debug.WriteLine("Connection opened for OrderDetails insert.");

                    string insertQuery = "INSERT INTO OrderDetails (ReservationID, MenuItemID, Quantity, ItemPrice, Subtotal) VALUES (@ReservationID, @MenuItemID, @Quantity, @ItemPrice, @Subtotal)";
                    using (SqlCommand command = new SqlCommand(insertQuery, connection))
                    {
                        command.Parameters.AddWithValue("@ReservationID", reservationId);
                        command.Parameters.AddWithValue("@MenuItemID", menuItemId);
                        command.Parameters.AddWithValue("@Quantity", quantity);
                        command.Parameters.AddWithValue("@ItemPrice", itemPrice);
                        command.Parameters.AddWithValue("@Subtotal", subtotal);

                        int rowsAffected = command.ExecuteNonQuery();
                        Debug.WriteLine($"Rows affected by OrderDetails insert: {rowsAffected}");

                        if (rowsAffected > 0)
                        {
                            Debug.WriteLine("Order details inserted successfully.");
                        }
                        else
                        {
                            Debug.WriteLine("Order details insertion failed.");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error in InsertOrderDetails: {ex.Message}");
            }
        }

        private void paidamount_TextChanged(object sender, EventArgs e)
        {
         
        }


        private void paidamount_KeyPress(object sender, KeyPressEventArgs e)
        {
           
        }


        private void panel1_Paint(object sender, PaintEventArgs e)
        {

        }

      

        private void minusbtn_Click(object sender, EventArgs e)
        {
            this.WindowState = FormWindowState.Minimized; // Minimize the form to the taskbar
        }

        private void panel3_Paint(object sender, PaintEventArgs e)
        {


        }

        private void button1_Click(object sender, EventArgs e)
        {
            Addorders addorders = new Addorders(_username);
            this.Hide();
            addorders.ShowDialog();
            this.Close();   
        }

        private void DatenTimetxt_TextChanged(object sender, EventArgs e)
        {
            try
            {
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    connection.Open();

                    // Query to get the current date and time from the database
                    string query = "SELECT GETDATE()";

                    using (SqlCommand command = new SqlCommand(query, connection))
                    {
                        object result = command.ExecuteScalar();
                        if (result != null)
                        {
                            // Set the TextBox value to the current date and time
                            DatenTimetxt.Text = Convert.ToDateTime(result).ToString("yyyy-MM-dd HH:mm:ss");
                        }
                        else
                        {
                            MessageBox.Show("Failed to retrieve the current date and time.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"An error occurred: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void button2_Click(object sender, EventArgs e)
        {
            AddPayment addPayment = new AddPayment(_username);
            this.Hide();    
            addPayment.ShowDialog();        
            this.Close();   
        }





        private string NormalizeArabicText(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return text;

            return text
                .Replace('أ', 'ا')  // Normalize 'أ' to 'ا'
                .Replace('إ', 'ا')  // Normalize 'إ' to 'ا'
                .Replace('آ', 'ا')  // Normalize 'آ' to 'ا'
               
               
                .Replace('ة', 'ه'); // Normalize 'ة' to 'ه'
        }

        private string ReverseNormalizeArabicText(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return text;

            return text
                .Replace('ا', 'أ')  // Reverse normalize 'ا' to 'أ'
                .Replace('ا', 'إ')  // Reverse normalize 'ا' to 'إ'
                .Replace('ا', 'آ')  // Reverse normalize 'ا' to 'آ'

                .Replace('ه', 'ة');  // Reverse normalize 'ه' to 'ة'
               
        }




        private void ConfigureNameAutoComplete()
        {
            AutoCompleteStringCollection autoCompleteCollection = new AutoCompleteStringCollection();
            string query = "SELECT Name FROM Customer";

            using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
            {
                using (SqlCommand command = new SqlCommand(query, connection))
                {
                    try
                    {
                        connection.Open();
                        using (SqlDataReader reader = command.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                string name = reader.GetString(0);
                                // Add both normalized and reverse-normalized versions to the collection
                                autoCompleteCollection.Add(NormalizeArabicText(name));
                                autoCompleteCollection.Add(ReverseNormalizeArabicText(name));
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show("An error occurred: " + ex.Message);
                    }
                }
            }

            nametxt.AutoCompleteMode = AutoCompleteMode.SuggestAppend;
            nametxt.AutoCompleteSource = AutoCompleteSource.CustomSource;
            nametxt.AutoCompleteCustomSource = autoCompleteCollection;

            nametxt.KeyDown += Nametxt_KeyDown;
        }


        private async void Nametxt_KeyDown(object sender, KeyEventArgs e)
        {
            // Check if the Enter key was pressed
            if (e.KeyCode == Keys.Enter)
            {
                // Avoid processing when the suggestions are not visible
                if (nametxt.AutoCompleteMode != AutoCompleteMode.None)
                {
                    e.SuppressKeyPress = true; // Prevent the default behavior of the Enter key
                    await SearchUserByNameAsync(nametxt.Text);
                }
            }
        }
        private async void Nametxt_TextChanged(object sender, EventArgs e)
        {
            if (nametxt.AutoCompleteMode == AutoCompleteMode.None)
            {
                await SearchUserByNameAsync(nametxt.Text);
            }
        }



        // Handle the TextChanged event to dynamically update suggestions
       




       

        private async void nametxt_TextChanged(object sender, EventArgs e)
        {


        }

        private async void nametxt_Leave(object sender, EventArgs e)
        {

            await SearchUserByNameAsync(nametxt.Text);

        }

        private async Task SearchUserByNameAsync(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
            {
               
                return;
            }

            // Normalize the input name
            string normalizedInput = NormalizeArabicText(name);
            Debug.WriteLine($"Normalized Input: {normalizedInput}");

                        string query = @"
            SELECT CustomerID, Phonenumber, Name
            FROM Customer 
            WHERE Name LIKE '%' + @Name + '%' OR dbo.NormalizeArabicText(Name) LIKE '%' + dbo.NormalizeArabicText(@Name) + '%'
";

            using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
            {
                using (SqlCommand command = new SqlCommand(query, connection))
                {
                    // Pass the normalized input to the query
                    command.Parameters.AddWithValue("@Name", normalizedInput);

                    Debug.WriteLine($"Query: {query}");
                    Debug.WriteLine($"Parameter @Name: {normalizedInput}");

                    try
                    {
                        await connection.OpenAsync();
                        using (SqlDataReader reader = await command.ExecuteReaderAsync())
                        {
                            if (await reader.ReadAsync())
                            {
                                string id = reader["CustomerId"]?.ToString() ?? "N/A";
                                string mobileNumber = reader["Phonenumber"]?.ToString() ?? "N/A";
                                string names = reader["Name"]?.ToString() ?? "N/A";


                                if (InvokeRequired)
                                {
                                    Invoke(new Action(() =>
                                    {

                                        Phonenumbertxt.Text = mobileNumber;
                                        nametxt.Text = names;

                                    }));
                                }
                                else
                                {

                                    Phonenumbertxt.Text = mobileNumber;
                                    nametxt.Text = names;

                                }

                                LockCustomerFields();
                            }
                           
                        }
                    }
                    catch (SqlException ex)
                    {
                        MessageBox.Show("A SQL error occurred: " + ex.Message);
                        Debug.WriteLine($"SQL Exception: {ex.Message}");
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show("An error occurred: " + ex.Message);
                        Debug.WriteLine($"Exception: {ex.Message}");
                    }
                }
            }
        }



        private void quantitytxt_TextChanged(object sender, EventArgs e)
        {

        }
        private async void Phonenumbertxt_Leave(object sender, EventArgs e)
        {
            await SearchUserAsync(Phonenumbertxt.Text);
        }

        private async void Phonenumbertxt_KeyDown(object sender, KeyEventArgs e)
        {
            // Check if the Enter key was pressed
            if (e.KeyCode == Keys.Enter)
            {
                // Avoid processing when the suggestions are not visible
                if (Phonenumbertxt.AutoCompleteMode != AutoCompleteMode.None)
                {
                    e.SuppressKeyPress = true; // Prevent the default behavior of the Enter key
                    await SearchUserAsync(Phonenumbertxt.Text);
                }
            }
        }


        private void ConfigureAutoComplete()
        {
            AutoCompleteStringCollection autoCompleteCollection = new AutoCompleteStringCollection();
            string query = "SELECT Phonenumber FROM Customer";

            using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
            {
                using (SqlCommand command = new SqlCommand(query, connection))
                {
                    try
                    {
                        connection.Open();
                        using (SqlDataReader reader = command.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                string mobileNumber = reader.GetString(0);
                                autoCompleteCollection.Add(mobileNumber);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show("An error occurred: " + ex.Message);
                    }
                }
            }

            Phonenumbertxt.AutoCompleteMode = AutoCompleteMode.SuggestAppend;
            Phonenumbertxt.AutoCompleteSource = AutoCompleteSource.CustomSource;
            Phonenumbertxt.AutoCompleteCustomSource = autoCompleteCollection;

            Phonenumbertxt.KeyDown += Phonenumbertxt_KeyDown;
        }


        private async Task SearchUserAsync(string mobileNumber)
        {
            // Validate phone number
            if (string.IsNullOrWhiteSpace(mobileNumber) || mobileNumber.Length != 11 || !mobileNumber.All(char.IsDigit))
            {
              
                return;
            }

            string query = "SELECT TOP 1 CustomerID, Name FROM Customer WHERE PhoneNumber = @MobileNumber";

            using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
            {
                using (SqlCommand command = new SqlCommand(query, connection))
                {
                    command.Parameters.AddWithValue("@MobileNumber", mobileNumber);

                    try
                    {
                        await connection.OpenAsync();
                        using (SqlDataReader reader = await command.ExecuteReaderAsync())
                        {
                            if (await reader.ReadAsync())
                            {
                                // Populate the fields with the retrieved data
                                nametxt.Text = reader.GetString(1);
                                LockCustomerFields();
                            }
                            else
                            {
                              
                                // Optionally reset fields here
                                // ResetUserFields();
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show("An error occurred: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                }
            }
        }


        private void Phonenumbertxt_KeyPress(object sender, KeyPressEventArgs e)
        {
            // Allow control characters (backspace, enter, etc.)
            if (!char.IsControl(e.KeyChar) && !char.IsDigit(e.KeyChar))
            {
                // If the character is not a control character or a digit, block it
                e.Handled = true;
            }
        }

        private void button3_Click(object sender, EventArgs e)
        {

           ResetForm();
        }


        private void ResetForm()
        {
          

            nametxt.Clear();
           addnewcustomerbtn.Enabled = true;
            nametxt.Enabled= true;
            Phonenumbertxt.Enabled= true;
            Resturantnamecombo.Enabled = false;
            reservationdateandtime.Enabled = true;
            importanttxt.Enabled = true;
           
            capacitytxt.Enabled = true;
            Reservationdatabtn.Enabled = true;
            Phonenumbertxt.Clear();
            Resturantnamecombo.Text= "";
            capacitytxt.Text = "";
            itemmenucombo.Text = ""; // Reset selected item
            quantitytxt.Text = "1";
            paidamount.Clear();
            reservationnumberlabel.Text = "";
            reservationidtxt.Text = "";
            totalPrice = 0;
            totalPriceLabel.Text = "";
            notestxt.Text = "";
            importanttxt.Text = "";
            ClearMenuItems();








            // quantitytxt.Value = 1; // If it's a NumericUpDown

            // Clear all child controls in the menu items panel
            menuitemspanel.Controls.Clear();




        }

        private void button4_Click(object sender, EventArgs e)
        {
            ReservationsReport reservationsReport = new ReservationsReport(_username);
            this.Hide();
            reservationsReport.ShowDialog();
            this.Close();
        }

        private void button5_Click(object sender, EventArgs e)
        {
            SpotCheck spotCheck = new SpotCheck(_username);
            this.Hide();
            spotCheck.ShowDialog();
            this.Close();   
        }

        private void RemainingCapacitylabel_Click(object sender, EventArgs e)
        {

        }

        private void button6_Click(object sender, EventArgs e)
        {
            Editorder editorder = new Editorder(_username);
            this.Hide();
            editorder.ShowDialog();
            this.Close();
        }

        private void button7_Click(object sender, EventArgs e)
        {
            DailyReports dailyReports = new DailyReports(_username);
            this.Hide();
            dailyReports.ShowDialog();
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
        private void backkbtn_Click(object sender, EventArgs e)
        {
            NavigateToForm(5, new Navigation(_username));
        }

        private void label4_Click(object sender, EventArgs e)
        {
            Login login = new Login();
            this.Hide();
            login.ShowDialog();
            this.Close();
        }

        private void notestxt_TextChanged(object sender, EventArgs e)
        {

        }

        // Declare a global variable to store the selected payment method
        private string paymentMethod = "Cash"; // Default to Cash

        private void Cashradiobtn_CheckedChanged(object sender, EventArgs e)
        {
            if (Cashradiobtn.Checked) // Check if the Cash radio button is selected
            {
                paymentMethod = "Cash";
              
            }
        }

        private void Visaradiobtn_CheckedChanged(object sender, EventArgs e)
        {
            if (Visaradiobtn.Checked) // Check if the Visa radio button is selected
            {
                paymentMethod = "Visa";
            
            }
        }

        private void nametxt_TextChanged_1(object sender, EventArgs e)
        {

        }

        private void panel3_Paint_1(object sender, PaintEventArgs e)
        {

        }

        private void radioButton1_CheckedChanged(object sender, EventArgs e)
        {
            if (radioButton1.Checked) // Check if the Visa radio button is selected
            {
                paymentMethod = "Online";

            }
        }
    }
































    public class ComboboxItem
    {
        public string Text { get; set; }
        public int Value { get; set; }
        public int RemainingCapacity { get; set; }  // Store the remaining capacity
        public override string ToString() => Text;
    }

}



