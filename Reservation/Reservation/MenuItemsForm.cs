using System;
using System.Data;
using System.Data.SqlClient;
using System.Windows.Forms;

namespace Reservation
{
    public partial class MenuItemsForm : Form
    {
        private int selectedItemID = 0;

        // 1. Field to store the current logged-in user
        private string _username;

        // 2. Constructor modified to accept the username
        public MenuItemsForm(string username)
        {
            InitializeComponent();
            _username = username;
        }

        private void MenuItemsForm_Load(object sender, EventArgs e)
        {
            LoadData();
        }

        private void LoadData()
        {
            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    conn.Open();
                    string query = "SELECT MenuItemID, ItemName, ItemPrice, IsActive FROM Menu";
                    SqlDataAdapter da = new SqlDataAdapter(query, conn);
                    DataTable dt = new DataTable();
                    da.Fill(dt);
                    dgvMenu.DataSource = dt;

                    if (dgvMenu.Columns["MenuItemID"] != null)
                    {
                        dgvMenu.Columns["MenuItemID"].Visible = false;
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Error loading data: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }

        private void btnAdd_Click(object sender, EventArgs e)
        {
            if (string.IsNullOrWhiteSpace(txtName.Text) || string.IsNullOrWhiteSpace(txtPrice.Text))
            {
                MessageBox.Show("Please fill all fields", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    conn.Open();

                    // --- 1. Perform Add ---
                    string insertData = "INSERT INTO Menu (ItemName, ItemPrice, IsActive) VALUES (@name, @price, @status)";
                    using (SqlCommand cmd = new SqlCommand(insertData, conn))
                    {
                        cmd.Parameters.AddWithValue("@name", txtName.Text.Trim());
                        cmd.Parameters.AddWithValue("@price", Convert.ToDecimal(txtPrice.Text.Trim()));
                        cmd.Parameters.AddWithValue("@status", chkIsActive.Checked);
                        cmd.ExecuteNonQuery();
                    }

                    // --- 2. Log Action ---
                    string logQuery = "INSERT INTO UserLog (CashierName, Action, DateAndTime) VALUES (@CashierName, @Action, GETDATE())";
                    using (SqlCommand logCommand = new SqlCommand(logQuery, conn))
                    {
                        string statusStr = chkIsActive.Checked ? "Active" : "Inactive";
                        // Added status to the log here
                        string logDetails = $"Added New Item: {txtName.Text.Trim()}, Price: {txtPrice.Text.Trim()}, Status: {statusStr}";

                        logCommand.Parameters.AddWithValue("@CashierName", _username);
                        logCommand.Parameters.AddWithValue("@Action", logDetails);
                        logCommand.ExecuteNonQuery();
                    }

                    MessageBox.Show("Item Added Successfully!", "Information", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    LoadData();
                    ClearFields();
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Error adding item: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }

        private void btnUpdate_Click(object sender, EventArgs e)
        {
            if (selectedItemID == 0)
            {
                MessageBox.Show("Please select an item first.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
            {
                try
                {
                    conn.Open();

                    // --- 1. Detect Status Change ---
                    // We get the original status from the DataGridView (which holds the data before the update)
                    bool oldStatus = false;
                    foreach (DataGridViewRow row in dgvMenu.Rows)
                    {
                        if (Convert.ToInt32(row.Cells["MenuItemID"].Value) == selectedItemID)
                        {
                            oldStatus = Convert.ToBoolean(row.Cells["IsActive"].Value);
                            break;
                        }
                    }

                    bool newStatus = chkIsActive.Checked;
                    string statusLogPart = "";

                    // Check if status changed
                    if (oldStatus != newStatus)
                    {
                        string fromState = oldStatus ? "Active" : "Inactive";
                        string toState = newStatus ? "Active" : "Inactive";
                        statusLogPart = $" | Status Changed from {fromState} to {toState}";
                    }
                    else
                    {
                        // If status didn't change, just mention current status
                        statusLogPart = $" | Status: {(newStatus ? "Active" : "Inactive")}";
                    }

                    // --- 2. Perform the Update Operation ---
                    string updateData = "UPDATE Menu SET ItemName = @name, ItemPrice = @price, IsActive = @status WHERE MenuItemID = @id";
                    using (SqlCommand cmd = new SqlCommand(updateData, conn))
                    {
                        cmd.Parameters.AddWithValue("@name", txtName.Text.Trim());
                        cmd.Parameters.AddWithValue("@price", Convert.ToDecimal(txtPrice.Text.Trim()));
                        cmd.Parameters.AddWithValue("@status", chkIsActive.Checked);
                        cmd.Parameters.AddWithValue("@id", selectedItemID);
                        cmd.ExecuteNonQuery();
                    }

                    // --- 3. Log the Action ---
                    string logQuery = "INSERT INTO UserLog (CashierName, Action, DateAndTime) VALUES (@CashierName, @Action, GETDATE())";
                    using (SqlCommand logCommand = new SqlCommand(logQuery, conn))
                    {
                        // Construct the full log message
                        string logDetails = $"Updated Item ID: {selectedItemID}, Name: {txtName.Text.Trim()}, Price: {txtPrice.Text.Trim()}{statusLogPart}";

                        logCommand.Parameters.AddWithValue("@CashierName", _username);
                        logCommand.Parameters.AddWithValue("@Action", logDetails);
                        logCommand.ExecuteNonQuery();
                    }

                    MessageBox.Show("Item Updated Successfully!", "Information", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    LoadData();
                    ClearFields();
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Error updating item: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }
        private void btnDelete_Click(object sender, EventArgs e)
        {
            if (selectedItemID == 0)
            {
                MessageBox.Show("Please select an item first.", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            if (MessageBox.Show("Are you sure you want to delete this item?", "Confirmation", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
            {
                using (SqlConnection conn = new SqlConnection(DatabaseConfig.connectionString))
                {
                    try
                    {
                        conn.Open();

                        // --- 1. Perform the Delete Operation ---
                        string deleteData = "DELETE FROM Menu WHERE MenuItemID = @id";
                        // Store name before deleting for the log
                        string deletedItemName = txtName.Text;

                        using (SqlCommand cmd = new SqlCommand(deleteData, conn))
                        {
                            cmd.Parameters.AddWithValue("@id", selectedItemID);
                            cmd.ExecuteNonQuery();
                        }

                        // --- 2. Log the Action ---
                        string logQuery = "INSERT INTO UserLog (CashierName, Action, DateAndTime) VALUES (@CashierName, @Action, GETDATE())";
                        using (SqlCommand logCommand = new SqlCommand(logQuery, conn))
                        {
                            string logDetails = $"Deleted Menu Item ID: {selectedItemID}, Name was: {deletedItemName}";

                            logCommand.Parameters.AddWithValue("@CashierName", _username);
                            logCommand.Parameters.AddWithValue("@Action", logDetails);
                            logCommand.ExecuteNonQuery();
                        }

                        MessageBox.Show("Item Deleted Successfully!", "Information", MessageBoxButtons.OK, MessageBoxIcon.Information);
                        LoadData();
                        ClearFields();
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show("Error deleting item: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                }
            }
        }

        private void btnClear_Click(object sender, EventArgs e)
        {
            ClearFields();
        }

        private void ClearFields()
        {
            txtName.Text = "";
            txtPrice.Text = "";
            chkIsActive.Checked = true;
            selectedItemID = 0;
            dgvMenu.ClearSelection();
        }

        private void dgvMenu_CellClick(object sender, DataGridViewCellEventArgs e)
        {
            if (e.RowIndex != -1)
            {
                DataGridViewRow row = dgvMenu.Rows[e.RowIndex];
                selectedItemID = Convert.ToInt32(row.Cells["MenuItemID"].Value);
                txtName.Text = row.Cells["ItemName"].Value.ToString();
                txtPrice.Text = row.Cells["ItemPrice"].Value.ToString();
                chkIsActive.Checked = Convert.ToBoolean(row.Cells["IsActive"].Value);
            }
        }



        private void backkbtn_Click(object sender, EventArgs e)
        {
            Navigation navigation = new Navigation(_username);
            this.Hide();
            navigation.ShowDialog();
            this.Close();
        }
    }
}