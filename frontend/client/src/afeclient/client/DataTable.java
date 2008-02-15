package afeclient.client;



import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.Widget;

/**
 * A table to display data from JSONObjects.  Each row displays data from one 
 * JSONObject.  A header row with column titles is automatically generated, and
 * support is included for adding other arbitrary header rows.
 * <br><br>
 * Styles:
 * <ul>
 * <li>.data-table - the entire table
 * <li>.data-row-header - the column title row
 * <li>.data-row-one/.data-row-two - data row styles.  These two are alternated.
 * </ul>
 */
public class DataTable extends Composite {
    public static final String HEADER_STYLE = "data-row-header";
    public static final String CLICKABLE_STYLE = "data-row-clickable";
    
    protected FlexTable table;
    
    protected String[][] columns;
    protected int headerRow = 0;
    protected boolean clickable = false;

    /**
     * @param columns An array specifying the name of each column and the field
     * to which it corresponds.  The array should have the form
     * {{'field_name1', 'Column Title 1'}, 
     *  {'field_name2', 'Column Title 2'}, ...}.
     */ 
    public DataTable(String[][] columns) {
        this.columns = columns;
        table = new FlexTable();
        initWidget(table);
        
        table.setCellSpacing(0);
        table.setCellPadding(0);
        table.setStyleName("data-table");

        for (int i = 0; i < columns.length; i++) {
            table.setText(0, i, columns[i][1]);
        }

        table.getRowFormatter().setStylePrimaryName(0, HEADER_STYLE);
    }

    protected void setRowStyle(int row) {
        table.getRowFormatter().setStyleName(row, "data-row");
        if ((row & 1) == 0) {
            table.getRowFormatter().addStyleName(row, "data-row-alternate");
        }
        if (clickable) {
            table.getRowFormatter().addStyleName(row, CLICKABLE_STYLE);
        }
    }
    
    public void setClickable(boolean clickable) {
        this.clickable = clickable;
        for(int i = headerRow + 1; i < table.getRowCount(); i++)
            setRowStyle(i);
    }

    /**
     * Clear all data rows from the table.  Leaves the header rows intact.
     */
    public void clear() {
        while (getRowCount() > 0) {
            removeRow(0);
        }
    }
    
    /**
     * This gets called for every JSONObject that gets added to the table using
     * addRow().  This allows subclasses to customize objects before they are 
     * added to the table, for example to reformat fields or generate new 
     * fields from the existing data.
     * @param row The row object about to be added to the table.
     */
    protected void preprocessRow(JSONObject row) {}
    
    protected String getTextForValue(JSONValue value) {
        if (value.isNumber() != null)
            return Integer.toString((int) value.isNumber().getValue());
        else if (value.isString() != null)
            return  value.isString().stringValue();
        else if (value.isNull() != null)
            return "";
        else
            throw new IllegalArgumentException(value.toString());
    }
    
    protected String[] getRowText(JSONObject row) {
        String[] rowText = new String[columns.length];
        for (int i = 0; i < columns.length; i++) {
            String columnKey = columns[i][0];
            JSONValue columnValue = row.get(columnKey);
            rowText[i] = getTextForValue(columnValue);
        }
        return rowText;
    }
    
    /**
     * Add a row from an array of Strings, one String for each column.
     * @param rowData Data for each column, in left-to-right column order.
     */
    public void addRowFromData(String[] rowData) {
        int row = table.getRowCount();
        for(int i = 0; i < columns.length; i++)
            table.setHTML(row, i, rowData[i]);
        setRowStyle(row);
    }

    /**
     * Add a row from a JSONObject.  Columns will be populated by pulling fields
     * from the objects, as dictated by the columns information passed into the
     * DataTable constructor.
     */
    public void addRow(JSONObject row) {
        preprocessRow(row);
        addRowFromData(getRowText(row));
    }
    
    /**
     * Add all objects in a JSONArray.
     * @param rows An array of JSONObjects
     * @throws IllegalArgumentException if any other type of JSONValue is in the
     * array.
     */
    public void addRows(JSONArray rows) {
        for (int i = 0; i < rows.size(); i++) {
            JSONObject row = rows.get(i).isObject();
            if (row == null)
                throw new IllegalArgumentException("rows must be JSONObjects");
            addRow(row);
        }
    }

    /**
     * Remove a data row from the table.
     * @param row The index of the row, where the first data row is indexed 0.
     * Header rows are ignored.
     */
    public void removeRow(int row) {
        int realRow = row + getHeaderRowCount();
        table.removeRow(realRow);
        for(int i = realRow; i < table.getRowCount(); i++)
            setRowStyle(i);
    }
    
    /**
     * Returns the number of data rows in the table.  The actual number of 
     * visible table rows is more than this, due to the header rows.
     */
    public int getRowCount() {
        return table.getRowCount() - getHeaderRowCount();
    }

    /**
     * Adds a header row to the table.  This is an extra row that is added above
     * the row of column titles and below any other header rows that have been
     * added.  The row consists of a single cell.
     * @param widget A widget to add to the cell.
     * @return The row index of the new header row.
     */
    public int addHeaderRow(Widget widget) {
        int row = table.insertRow(headerRow);
        headerRow++;
        table.getFlexCellFormatter().setColSpan(row, 0, columns.length);
        table.setWidget(row, 0, widget);
        return row;
    }
    
    /**
     * Returns the number of header rows, including the column title row.
     */
    public int getHeaderRowCount() {
        return headerRow + 1;
    }
}
