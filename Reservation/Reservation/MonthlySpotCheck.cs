using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Data.SqlClient;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Printing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Reservation
{
    public partial class MonthlySpotCheck : Form
    {
        private float _initialFormWidth;
        private float _initialFormHeight;
        private ControlInfo[] _controlsInfo;



        private string _username;
        public MonthlySpotCheck(string username)
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


        private void dashboard_btn_Click(object sender, EventArgs e)
        {
            NavigateToForm(2, new MonthlyReport(_username));



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

                int selectedYear = dateTimePicker1.Value.Year;
                int selectedMonth = dateTimePicker1.Value.Month;
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
                WHERE YEAR(PaymentDate) = @Year AND MONTH(PaymentDate) = @Month
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
               WHERE YEAR(PaymentDate) = @Year AND MONTH(PaymentDate) = @Month
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
               WHERE YEAR(PaymentDate) = @Year AND MONTH(PaymentDate) = @Month
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
                WHERE YEAR(PaymentDate) = @Year AND MONTH(PaymentDate) = @Month
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
                       

                        command.Parameters.AddWithValue("@Year", selectedYear);
                        command.Parameters.AddWithValue("@Month", selectedMonth);
                        if (GlobalUser.Role == 1)
                        {

                            command.Parameters.AddWithValue("@Username", usertxt.Text);

                        }
                        else
                        {

                            command.Parameters.AddWithValue("@Username", _username);

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
                int selectedYear = dateTimePicker1.Value.Year;
                int selectedMonth = dateTimePicker1.Value.Month;

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
                  WHERE YEAR(PaymentDate) = @Year AND MONTH(PaymentDate) = @Month
                   
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
             WHERE YEAR(PaymentDate) = @Year AND MONTH(PaymentDate) = @Month
                   
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
                 WHERE YEAR(PaymentDate) = @Year AND MONTH(PaymentDate) = @Month
                  
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
                WHERE YEAR(PaymentDate) = @Year AND MONTH(PaymentDate) = @Month
                    
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
                        
                        command.Parameters.AddWithValue("@Year", selectedYear);
                        command.Parameters.AddWithValue("@Month", selectedMonth);
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
            UserLog addPayment = new UserLog(_username);
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
            currentPageIndex = 0;

            // Manually define the column order you want for printing
            columnsToPrint = new List<DataGridViewColumn>
    {
                  reservationsview.Columns["PaymentMethod"],
        reservationsview.Columns["Cashiername"],

        reservationsview.Columns["PaymentDate"],
        reservationsview.Columns["PaidAmount"],
        reservationsview.Columns["ReservationID"],
        reservationsview.Columns["Name"],
        reservationsview.Columns["PaymentID"]
      
    };

            PrintDocument printDocument = new PrintDocument();
            printDocument.PrintPage += PrintDocument_PrintPage;

            // Set landscape mode
            printDocument.DefaultPageSettings.Landscape = true;

            PrintDialog printDialog = new PrintDialog
            {
                Document = printDocument
            };

            if (printDialog.ShowDialog() == DialogResult.OK)
            {
                printDocument.Print();
            }
        }

        private void PrintDocument_PrintPage(object sender, PrintPageEventArgs e)
        {
            int totalWidth = columnsToPrint.Sum(col => col.Width);
            int printableWidth = e.MarginBounds.Width;
            float scaleFactor = (float)printableWidth / totalWidth;

            rowsPerPage = (int)((e.MarginBounds.Height - e.MarginBounds.Top) / (reservationsview.RowTemplate.Height + 5));

            string headerText = "تقرير يومي";
            string reportDateText = $"التاريخ: {dateTimePicker1.Value.Date.ToShortDateString()}";

            float y = e.MarginBounds.Top - 30;
            float x = e.MarginBounds.Left;

            Font headerFont = new Font(reservationsview.Font.FontFamily, 14, FontStyle.Bold);
            Font dateFont = new Font(reservationsview.Font.FontFamily, 12, FontStyle.Regular);
            Font cellFont = new Font(reservationsview.Font.FontFamily, 10, FontStyle.Regular);

            SizeF headerSize = e.Graphics.MeasureString(headerText, headerFont);
            SizeF dateSize = e.Graphics.MeasureString(reportDateText, dateFont);

            float headerX = e.MarginBounds.Right - headerSize.Width;
            float dateX = e.MarginBounds.Right - dateSize.Width;

            e.Graphics.DrawString(headerText, headerFont, Brushes.Black, new PointF(headerX, y));
            e.Graphics.DrawString(reportDateText, dateFont, Brushes.Black, new PointF(dateX, y + headerSize.Height + 5));

            y += (int)headerSize.Height + (int)dateSize.Height + 30;

            // Print column headers
            x = e.MarginBounds.Left;
            foreach (var column in columnsToPrint)
            {
                int columnWidth = (int)(column.Width * scaleFactor);

                // Ensure Payment Date column has enough width
                if (column.Name == "PaymentDate")
                {
                    columnWidth = Math.Max(columnWidth, 150); // Increase width if needed
                }

                RectangleF rect = new RectangleF(x, y, columnWidth, reservationsview.RowTemplate.Height);
                string headerColumnText = columnHeaderMappings.ContainsKey(column.Name)
                    ? columnHeaderMappings[column.Name]
                    : column.HeaderText;

                e.Graphics.DrawString(headerColumnText, reservationsview.Font, Brushes.Black, rect,
                    new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center });

                x += columnWidth;
            }

            y += reservationsview.RowTemplate.Height + 5;

            int rowsPrinted = 0;
            for (int i = currentPage * rowsPerPage; i < reservationsview.Rows.Count; i++)
            {
                if (reservationsview.Rows[i].IsNewRow) continue;

                x = e.MarginBounds.Left;
                foreach (var column in columnsToPrint)
                {
                    var cell = reservationsview.Rows[i].Cells[column.Name];
                    int cellWidth = (int)(column.Width * scaleFactor);

                    if (column.Name == "PaymentDate")
                    {
                        cellWidth = Math.Max(cellWidth, 150); // Ensure Payment Date is not truncated
                    }

                    RectangleF rect = new RectangleF(x, y, cellWidth, reservationsview.RowTemplate.Height);

                    // Apply proper text formatting
                    StringFormat cellFormat = new StringFormat
                    {
                        Alignment = StringAlignment.Center,
                        LineAlignment = StringAlignment.Center,
                        FormatFlags = StringFormatFlags.LineLimit // Ensures text wraps if needed
                    };

                    e.Graphics.DrawString(cell.Value?.ToString(), cellFont, Brushes.Black, rect, cellFormat);
                    x += cellWidth;
                }

                y += reservationsview.RowTemplate.Height + 5;
                rowsPrinted++;

                if (rowsPrinted >= rowsPerPage)
                {
                    currentPage++;
                    e.HasMorePages = true;
                    return;
                }
            }

            e.HasMorePages = false;
            currentPage = 0;
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

        private void button1_Click(object sender, EventArgs e)
        {
            NavigateToForm(2, new DailyReports(_username));
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

        private void button3_Click(object sender, EventArgs e)
        {
            DeletedReservations deletedReservations = new DeletedReservations(_username);
            this.Hide();
            deletedReservations.ShowDialog();
            this.Close();
        }




        private void ApplyFilter()
        {
            if (reservationsview.DataSource is DataTable dataTable)
            {
                string filter = "";

                if (!string.IsNullOrWhiteSpace(textBox1.Text) && int.TryParse(textBox1.Text, out int reservationId))
                {
                    filter = $"ReservationID = {reservationId}"; // Use '=' for integer comparison
                }

                // Apply the filter to the DataTable
                dataTable.DefaultView.RowFilter = filter;
            }
        }

        private void textBox1_TextChanged(object sender, EventArgs e)
        {
            ApplyFilter();
        }

        private void label3_Click(object sender, EventArgs e)
        {

        }
    }

}



