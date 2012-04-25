package autotest.common.table;


import autotest.common.Utils;
import autotest.common.ui.RightClickTable;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.ContextMenuEvent;
import com.google.gwt.event.dom.client.ContextMenuHandler;
import com.google.gwt.event.dom.client.DomEvent;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTMLTable;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

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
public class DataTable extends Composite implements ClickHandler, ContextMenuHandler {
    public enum WidgetType {
	CheckBox, ListBox
    }
    public static final String HEADER_STYLE = "data-row-header";
    public static final String CLICKABLE_STYLE = "data-row-clickable";
    public static final String HIGHLIGHTED_STYLE = "data-row-highlighted";
    public static final String WIDGET_COLUMN = "_WIDGET_COLUMN_";
    // use CLICKABLE_WIDGET_COLUMN for widget that expect to receive clicks.  The table will ignore
    // click events coming from these columns.
    public static final String CLICKABLE_WIDGET_COLUMN = "_CLICKABLE_WIDGET_COLUMN_";
    // for indexing into column subarrays (i.e. columns[1][COL_NAME])
    public static final int COL_NAME = 0, COL_TITLE = 1;

    public static interface DataTableListener {
        public void onRowClicked(int rowIndex, JSONObject row, boolean isRightClick);
    }

    protected RightClickTable table;

    protected String[][] columns;
    protected int headerRow = 0;
    protected boolean clickable = false;

    protected TableWidgetFactory widgetFactory = null;
    private List<DataTableListener> listeners = new ArrayList<DataTableListener>();

    // keep a list of JSONObjects corresponding to rows in the table
    protected List<JSONObject> jsonObjects = new ArrayList<JSONObject>();


    public static interface TableWidgetFactory {
        public Widget createWidget(int row, int cell, JSONObject rowObject, WidgetType type);
    }

    /**
     * @param columns An array specifying the name of each column and the field
     * to which it corresponds.  The array should have the form
     * {{'field_name1', 'Column Title 1'},
     *  {'field_name2', 'Column Title 2'}, ...}.
     */
    public DataTable(String[][] columns) {
        int rows = columns.length;
        this.columns = new String[rows][2];
        for (int i = 0; i < rows; i++) {
            System.arraycopy(columns[i], 0, this.columns[i], 0, 2);
        }

        table = new RightClickTable();
        initWidget(table);

        table.setCellSpacing(0);
        table.setCellPadding(0);
        table.setStylePrimaryName("data-table");
        table.addStyleDependentName("outlined");

        for (int i = 0; i < columns.length; i++) {
            table.setText(0, i, columns[i][1]);
        }

        table.getRowFormatter().setStylePrimaryName(0, HEADER_STYLE);
        table.addClickHandler(this);
    }

    /**
     * Causes the last column of the data table to fill the remainder of the width left in the
     * parent widget.
     */
    public void fillParent() {
        table.getColumnFormatter().setWidth(table.getCellCount(0) - 1, "100%");
    }

    public void setWidgetFactory(TableWidgetFactory widgetFactory) {
        this.widgetFactory = widgetFactory;
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
        while (table.getRowCount() > 1) {
            table.removeRow(1);
        }
        jsonObjects.clear();
    }

    /**
     * This gets called for every JSONObject that gets added to the table using
     * addRow().  This allows subclasses to customize objects before they are
     * added to the table, for example to reformat fields or generate new
     * fields from the existing data.
     * @param row The row object about to be added to the table.
     */
    protected void preprocessRow(JSONObject row) {}

    protected String[] getRowText(JSONObject row) {
        String[] rowText = new String[columns.length];
        for (int i = 0; i < columns.length; i++) {
            if (isWidgetColumn(i))
                continue;

            String columnKey = columns[i][0];
            JSONValue columnValue = row.get(columnKey);
            if (columnValue == null || columnValue.isNull() != null) {
                rowText[i] = "";
            } else {
                rowText[i] = Utils.jsonToString(columnValue);
            }
        }
        return rowText;
    }

    /**
     * Add a row from an array of Strings, one String for each column.
     * @param rowData Data for each column, in left-to-right column order.
     */
    protected void addRowFromData(String[] rowData) {
        int row = table.getRowCount();
        for(int i = 0; i < columns.length; i++) {
            if (isProfileColumn(i)) {
                table.setWidget(row, i, getWidgetForCell(row, i, WidgetType.ListBox));
            } else if(isWidgetColumn(i)) {
                table.setWidget(row, i, getWidgetForCell(row, i, WidgetType.CheckBox));
            } else {
                table.setText(row, i, rowData[i]);
            }
        }
        setRowStyle(row);
    }

    protected boolean isWidgetColumn(int column) {
        return columns[column][COL_NAME].equals(WIDGET_COLUMN) || isClickableWidgetColumn(column);
    }

    protected boolean isClickableWidgetColumn(int column) {
        return columns[column][COL_NAME].equals(CLICKABLE_WIDGET_COLUMN) || isProfileColumn(column);
    }

    protected boolean isProfileColumn(int column) {
        return columns[column][COL_NAME].equals("current_profile");
    }

    /**
     * Add a row from a JSONObject.  Columns will be populated by pulling fields
     * from the objects, as dictated by the columns information passed into the
     * DataTable constructor.
     */
    public void addRow(JSONObject row) {
        preprocessRow(row);
        jsonObjects.add(row);
        addRowFromData(getRowText(row));
    }

    /**
     * Add all objects in a JSONArray.
     * @param rows An array of JSONObjects
     * @throws IllegalArgumentException if any other type of JSONValue is in the
     * array.
     */
    public void addRows(List<JSONObject> rows) {
        for (JSONObject row : rows) {
            addRow(row);
        }
    }

    /**
     * Remove a data row from the table.
     * @param rowIndex The index of the row, where the first data row is indexed 0.
     * Header rows are ignored.
     */
    public void removeRow(int rowIndex) {
        jsonObjects.remove(rowIndex);
        int realRow = rowIndex + 1; // header row
        table.removeRow(realRow);
        for(int i = realRow; i < table.getRowCount(); i++)
            setRowStyle(i);
    }

    /**
     * Returns the number of data rows in the table.  The actual number of
     * visible table rows is more than this, due to the header row.
     */
    public int getRowCount() {
        return table.getRowCount() - 1;
    }

    /**
     * Get the JSONObject corresponding to the indexed row.
     */
    public JSONObject getRow(int rowIndex) {
        return jsonObjects.get(rowIndex);
    }

    /**
     * Set the JSONObject corresponding to the indexed row.
     */
    public void setRow(int rowIndex, JSONObject row) {
        jsonObjects.set(rowIndex, row);
    }

    public List<JSONObject> getAllRows() {
        return Collections.unmodifiableList(jsonObjects);
    }

    public void highlightRow(int row) {
        row++; // account for header row
        table.getRowFormatter().addStyleName(row, HIGHLIGHTED_STYLE);
    }

    public void unhighlightRow(int row) {
        row++; // account for header row
        table.getRowFormatter().removeStyleName(row, HIGHLIGHTED_STYLE);
    }

    public void sinkRightClickEvents() {
        table.addContextMenuHandler(this);
    }

    @Override
    public void onClick(ClickEvent event) {
        onCellClicked(event, false);
    }

    @Override
    public void onContextMenu(ContextMenuEvent event) {
        onCellClicked(event, true);
    }

    private void onCellClicked(DomEvent<?> event, boolean isRightClick) {
        HTMLTable.Cell tableCell = table.getCellForDomEvent(event);
        if (tableCell == null) {
            return;
        }

        int row = tableCell.getRowIndex();
        int cell = tableCell.getCellIndex();

        if (isClickableWidgetColumn(cell) && table.getWidget(row, cell) != null) {
            return;
        }

        onCellClicked(row, cell, isRightClick);
    }

    protected void onCellClicked(int row, int cell, boolean isRightClick) {
        if (row != headerRow) {
            notifyListenersClicked(row - headerRow - 1, isRightClick);
        }
    }

    public void addListener(DataTableListener listener) {
        listeners.add(listener);
    }

    public void removeListener(DataTableListener listener) {
        listeners.remove(listener);
    }

    protected void notifyListenersClicked(int rowIndex, boolean isRightClick) {
        JSONObject row = getRow(rowIndex);
        for (DataTableListener listener : listeners) {
            listener.onRowClicked(rowIndex, row, isRightClick);
        }
    }

    public void refreshWidgets() {
        for (int row = 1; row < table.getRowCount(); row++) {
            for (int column = 0; column < columns.length; column++) {
                if (!isWidgetColumn(column)) {
                    continue;
                }
                table.clearCell(row, column);
                if (isProfileColumn(column))
                    table.setWidget(row, column, getWidgetForCell(row, column, WidgetType.ListBox));
                else if (isWidgetColumn(column))
                    table.setWidget(row, column, getWidgetForCell(row, column, WidgetType.CheckBox));
            }
        }
    }

    private Widget getWidgetForCell(int row, int column, WidgetType type) {
        return widgetFactory.createWidget(row - 1, column, jsonObjects.get(row - 1), type);
    }
}
