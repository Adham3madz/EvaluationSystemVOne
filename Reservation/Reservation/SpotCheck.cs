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
    public partial class SpotCheck : Form
    {
        private float _initialFormWidth;
        private float _initialFormHeight;
        private ControlInfo[] _controlsInfo;



        private string _username;
        public SpotCheck(string username)
        {
            InitializeComponent();




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

            _username = username;


            ConfigureNameAutoComplete();
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
            Home home = new Home(_username);
            this.Hide();
            home.ShowDialog();
            this.Close();




        }
































        // Define a variable to store the total price





        // Method to fetch the price of the selected item from the Menu table



        // Event handler when a row is clicked






        private void menuitemspanel_Paint(object sender, PaintEventArgs e)
        {

        }

        private void Home_Load(object sender, EventArgs e)
        {
            cashiernamelabel.Text = _username;
           
            ConfigureNameAutoComplete();
            if (GlobalUser.Role == 1) {
                dateTimePicker1.Enabled = true;
                    }
        }






































        private void paidamount_TextChanged(object sender, EventArgs e)
        {

        }

        private void panel1_Paint(object sender, PaintEventArgs e)
        {

        }




        private void minusbtn_Click(object sender, EventArgs e)
        {
            this.WindowState = FormWindowState.Minimized; // Minimize the form to the taskbar
        }










        private void Fetchdatabtn_Click(object sender, EventArgs e)
        {

        }


        private void LoadReservations()
        {

            try
            {
                // Database connection string (update with your actual connection details)


                // Get the selected date from the DateTimePicker
                DateTime selectedDate = dateTimePicker1.Value.Date;

                // SQL query to fetch data filtered by ReservationDate
                string query = @"
                    SELECT 
                    PaymentID,
                    Name,
                    ReservationID,
                    PaidAmount,
                    PaymentDate,
                   
                    Cashiername,
                    PaymentMethod
                FROM 
                    vw_DailyPaymentsSummary
                WHERE 
                    CAST(PaymentDate AS DATE) = @PaymentDate 
                    AND Cashiername = @Username
                UNION ALL
                SELECT 
                    NULL AS PaymentID,
                    'Total Cash' AS Name,
                    NULL AS ReservationID,
                    SUM(PaidAmount) AS PaidAmount,
                    NULL AS PaymentDate,
                  
                    NULL AS Cashiername,
                    'Cash' AS PaymentMethod
                FROM 
                    vw_DailyPaymentsSummary
                WHERE 
                    CAST(PaymentDate AS DATE) = @PaymentDate 
                    AND Cashiername = @Username
                    AND PaymentMethod = 'Cash'
                UNION ALL
                SELECT 
                    NULL AS PaymentID,
                    'Total Visa' AS Name,
                    NULL AS ReservationID,
                    SUM(PaidAmount) AS PaidAmount,
                    NULL AS PaymentDate,
                  
                    NULL AS Cashiername,
                    'Visa' AS PaymentMethod
                FROM 
                    vw_DailyPaymentsSummary
                WHERE 
                    CAST(PaymentDate AS DATE) = @PaymentDate 
                    AND Cashiername = @Username
                    AND PaymentMethod = 'Visa'
                UNION ALL
                SELECT 
                    NULL AS PaymentID,
                    'Subtotal' AS Name,
                    NULL AS ReservationID,
                    SUM(PaidAmount) AS PaidAmount,
                    NULL AS PaymentDate,
                   
                    NULL AS Cashiername,
                    NULL AS PaymentMethod
                FROM 
                    vw_DailyPaymentsSummary
                WHERE 
                    CAST(PaymentDate AS DATE) = @PaymentDate 
                    AND Cashiername = @Username;
                            ";


                // Create a connection to the database
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    // Open the connection
                    connection.Open();

                    // Create a SQL command
                    using (SqlCommand command = new SqlCommand(query, connection))
                    {
                        // Add the parameter for the selected date
                        command.Parameters.AddWithValue("@Paymentdate", selectedDate);
                        if (GlobalUser.Role == 1)
                        {

                            command.Parameters.AddWithValue("@Username", usertxt.Text);

                        }
                        else
                        {

                            command.Parameters.AddWithValue("@Username",_username);

                        }

                        // Create a data adapter
                        using (SqlDataAdapter adapter = new SqlDataAdapter(command))
                        {
                            // Create a DataTable to load the results
                            DataTable dataTable = new DataTable();

                            // Fill the DataTable with the query results
                            adapter.Fill(dataTable);

                            // Set the DataSource of the DataGridView
                            reservationsview.DataSource = dataTable;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                // Show an error message if an exception occurs
                MessageBox.Show("An error occurred: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }



        private void LoadAllReservations()
        {

            try
            {
                // Database connection string (update with your actual connection details)


                // Get the selected date from the DateTimePicker
                DateTime selectedDate = dateTimePicker1.Value.Date;

                // SQL query to fetch data filtered by ReservationDate
                string query = @"
                    SELECT 
                    PaymentID,
                    Name,
                    ReservationID,
                    PaidAmount,
                    PaymentDate,
                   
                    Cashiername,
                    PaymentMethod
                FROM 
                    vw_DailyPaymentsSummary
                WHERE 
                    CAST(PaymentDate AS DATE) = @PaymentDate 
                   
                UNION ALL
                SELECT 
                    NULL AS PaymentID,
                    'Total Cash' AS Name,
                    NULL AS ReservationID,
                    SUM(PaidAmount) AS PaidAmount,
                    NULL AS PaymentDate,
                  
                    NULL AS Cashiername,
                    'Cash' AS PaymentMethod
                FROM 
                    vw_DailyPaymentsSummary
                WHERE 
                    CAST(PaymentDate AS DATE) = @PaymentDate 
                   
                    AND PaymentMethod = 'Cash'
                UNION ALL
                SELECT 
                    NULL AS PaymentID,
                    'Total Visa' AS Name,
                    NULL AS ReservationID,
                    SUM(PaidAmount) AS PaidAmount,
                    NULL AS PaymentDate,
                  
                    NULL AS Cashiername,
                    'Visa' AS PaymentMethod
                FROM 
                    vw_DailyPaymentsSummary
                WHERE 
                    CAST(PaymentDate AS DATE) = @PaymentDate 
                  
                    AND PaymentMethod = 'Visa'
                UNION ALL
                SELECT 
                    NULL AS PaymentID,
                    'Subtotal' AS Name,
                    NULL AS ReservationID,
                    SUM(PaidAmount) AS PaidAmount,
                    NULL AS PaymentDate,
                   
                    NULL AS Cashiername,
                    NULL AS PaymentMethod
                FROM 
                    vw_DailyPaymentsSummary
                WHERE 
                    CAST(PaymentDate AS DATE) = @PaymentDate 
                    
                            ";


                // Create a connection to the database
                using (SqlConnection connection = new SqlConnection(DatabaseConfig.connectionString))
                {
                    // Open the connection
                    connection.Open();

                    // Create a SQL command
                    using (SqlCommand command = new SqlCommand(query, connection))
                    {
                        // Add the parameter for the selected date
                        command.Parameters.AddWithValue("@Paymentdate", selectedDate);
                       // command.Parameters.AddWithValue("@Username", usertxt.Text);

                        // Create a data adapter
                        using (SqlDataAdapter adapter = new SqlDataAdapter(command))
                        {
                            // Create a DataTable to load the results
                            DataTable dataTable = new DataTable();

                            // Fill the DataTable with the query results
                            adapter.Fill(dataTable);

                            // Set the DataSource of the DataGridView
                            reservationsview.DataSource = dataTable;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                // Show an error message if an exception occurs
                MessageBox.Show("An error occurred: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void searchbtn_Click(object sender, EventArgs e)
        {
            if (GlobalUser.Role == 1)
            {

                usertxt.Enabled = true;
                // If usertxt has text, load specific reservations instead of all
                if (!string.IsNullOrWhiteSpace(usertxt.Text))
                {
                    LoadReservations();
                }
                else
                {
                    LoadAllReservations();
                }
            }
            else
            {
                LoadReservations();
            }
        }






        private void dateTimePicker1_ValueChanged(object sender, EventArgs e)
        {

        }

        private void button4_Click(object sender, EventArgs e)
        {
            ReservationsReport reservationsReport = new ReservationsReport(_username);
            this.Hide();
            reservationsReport.ShowDialog();
            this.Close();
        }

        private void button2_Click(object sender, EventArgs e)
        {
            AddPayment addPayment = new AddPayment(_username);
            this.Hide();
            addPayment.ShowDialog();
            this.Close();
        }

        private void button5_Click(object sender, EventArgs e)
        {

        }



        private int currentPageIndex = 0;
        private List<DataGridViewColumn> columnsToPrint;
        private int currentPage = 0; // Track the current page number
        private int rowsPerPage; // Number of rows per page
        private int totalRows; // Total number of rows

        private Dictionary<string, string> columnHeaderMappings = new Dictionary<string, string>
{

     { "Cashiername", "القائم بالحجز" },
    
    
    { "PaymentDate", "تاريخ الدفع" },
    { "PaidAmount", "المدفوع" },
   { "ReservationID", "رقم الحجز" },
    { "Name", "الاسم" },
    
    { "PaymentID", "رقم العمليه" }
};

        private void Printbtn_Click(object sender, EventArgs e)
        {
            List<Tuple<string, string, decimal>> payments = new List<Tuple<string, string, decimal>>();
            decimal totalCash = 0, totalVisa = 0, totalAmount = 0;
            string cashier = cashiernamelabel.Text;
            string date = DateTime.Now.ToString("yy-MM-dd HH:mm:ss");

            int totalRows = reservationsview.Rows.Count;
            int rowsToRemove = Math.Min(4, totalRows);

            for (int i = 0; i < totalRows - rowsToRemove; i++)
            {
                DataGridViewRow row = reservationsview.Rows[i];

              
                string paymentDate = row.Cells["PaymentDate"]?.Value != null
                    ? Convert.ToDateTime(row.Cells["PaymentDate"].Value).ToString("yy-MM-dd")
                    : "N/A";
                string amount = row.Cells["PaidAmount"]?.Value?.ToString() ?? "0";
                string resID = row.Cells["ReservationID"]?.Value?.ToString() ?? "-";
                string payID = row.Cells["PaymentID"]?.Value?.ToString() ?? "-";
                string paymentMethod = row.Cells["PaymentMethod"]?.Value?.ToString() ?? "N/A";

                if (decimal.TryParse(amount, out decimal parsedAmount))
                {
                    totalAmount += parsedAmount;
                    if (paymentMethod.Equals("Cash", StringComparison.OrdinalIgnoreCase))
                        totalCash += parsedAmount;
                    else if (paymentMethod.Equals("Visa", StringComparison.OrdinalIgnoreCase))
                        totalVisa += parsedAmount;
                }

                payments.Add(new Tuple<string, string, decimal>(resID, payID, parsedAmount));

               
            }

            PrintSpotCheckReceipt(payments, totalCash, totalVisa, totalAmount, cashier, date);
        }

        private void PrintSpotCheckReceipt(List<Tuple<string, string, decimal>> payments, decimal totalCash, decimal totalVisa, decimal totalAmount, string cashier, string date)
        {
            PrintDocument printDocument = new PrintDocument();
            printDocument.PrintPage += (sender, e) =>
            {
                float yPosition = 10;
                float leftMargin = 10;
                float rightMargin = e.PageBounds.Width - 10;
                float lineHeight = 25;
                Font font = new Font("Arial", 14);
                Font boldFont = new Font("Arial", 10, FontStyle.Bold);
                Font titleFont = new Font("Arial", 12, FontStyle.Bold);
                StringFormat rtlFormat = new StringFormat { Alignment = StringAlignment.Far };
                StringFormat leftAlignFormat = new StringFormat { Alignment = StringAlignment.Near };
                StringFormat centerFormat = new StringFormat { Alignment = StringAlignment.Center };

                e.Graphics.DrawString("Spot Check Receipt", titleFont, Brushes.Black, new PointF(e.PageBounds.Width / 2, yPosition), centerFormat);
                yPosition += 40;

                e.Graphics.DrawString($"Date: {date}", new Font("Arial", 8), Brushes.Black, new PointF(rightMargin, yPosition), rtlFormat);
                e.Graphics.DrawString($"Cashier: {cashier}", new Font("Arial", 8), Brushes.Black, new PointF(leftMargin, yPosition), leftAlignFormat);
                yPosition += lineHeight;

                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, rightMargin, yPosition);
                yPosition += 10;

                

              

                e.Graphics.DrawString($"Total Cash: {totalCash:N2}", boldFont, Brushes.Black, new PointF(leftMargin, yPosition), leftAlignFormat);
                yPosition += lineHeight;
                e.Graphics.DrawString($"Total Visa: {totalVisa:N2}", boldFont, Brushes.Black, new PointF(leftMargin, yPosition), leftAlignFormat);
                yPosition += lineHeight;
                e.Graphics.DrawString($"Total Amount: {totalAmount:N2}", titleFont, Brushes.Black, new PointF(leftMargin, yPosition), leftAlignFormat);
                yPosition += lineHeight;

                e.Graphics.DrawLine(Pens.Black, leftMargin, yPosition, rightMargin, yPosition);
                yPosition += 10;

                // Add the footer message
                string footerMessage = "شكرا على اختيارك دار الضيافة";
                e.Graphics.DrawString(footerMessage, font, Brushes.Black, e.PageBounds.Width / 2, yPosition, centerFormat);
                yPosition += 25;

                string selim = "Selim's For Software \n 01155003537";
                e.Graphics.DrawString(selim, new Font("Arial", 7, FontStyle.Bold), Brushes.Black, e.PageBounds.Width / 2, yPosition, centerFormat);
                yPosition += 5;
            };

            printDocument.Print();
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

        private void button1_Click(object sender, EventArgs e)
        {
            Home home = new Home(_username);
            this.Hide();
            home .ShowDialog();
            this.Close();
        }




        private void ConfigureNameAutoComplete()
        {
            AutoCompleteStringCollection autoCompleteCollection = new AutoCompleteStringCollection();
            string query = "SELECT FullName FROM Cashier";

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

            usertxt.AutoCompleteMode = AutoCompleteMode.SuggestAppend;
            usertxt.AutoCompleteSource = AutoCompleteSource.CustomSource;
            usertxt.AutoCompleteCustomSource = autoCompleteCollection;

          
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
            SELECT CashierID, FullName
            FROM Cashier 
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
                                string id = reader["CashierID"]?.ToString() ?? "N/A";
                               
                                string names = reader["FullName"]?.ToString() ?? "N/A";


                                if (InvokeRequired)
                                {
                                    Invoke(new Action(() =>
                                    {

                                       
                                        usertxt.Text = names;

                                    }));
                                }
                                else
                                {

                                   
                                    usertxt.Text = names;

                                }

                              
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

        private async void usertxt_TextChanged(object sender, EventArgs e)
        {
            if (usertxt.AutoCompleteMode == AutoCompleteMode.None)
            {
                await SearchUserByNameAsync(usertxt.Text);
            }
        }
    }

}



