package afeclient.client;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Set;
import java.util.Vector;

import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Image;
import com.google.gwt.user.client.ui.KeyboardListener;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.SourcesTableEvents;
import com.google.gwt.user.client.ui.TableListener;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

/**
 * Extended DataTable supporting client-side sorting, searching, filtering, and 
 * pagination.
 */
public class DynamicTable extends DataTable {
    public static final int NO_COLUMN = -1;
    public static final int ASCENDING = 1, DESCENDING = -1;
    public static final String ALL_VALUES = "All values";
    public static final String SORT_UP_IMAGE = "arrow_up.png",
                               SORT_DOWN_IMAGE = "arrow_down.png";
    
    interface DynamicTableListener {
        public void onRowClicked(int dataRow, int column);
    }
    
    interface Filter {
        public boolean isActive();
        public boolean acceptRow(String[] row);
        public void update();
    }
    
    class ColumnFilter implements Filter {
        public int column;
        public ListBox select = new ListBox();
        public boolean isManualChoices = false, isExactMatch = true;
        
        public ColumnFilter(int column) {
            this.column = column;
            select.setStylePrimaryName("filter-box");
        }
        
        public void setExactMatch(boolean isExactMatch) {
            this.isExactMatch = isExactMatch;
        }

        public String getSelectedValue() {
            return select.getItemText(select.getSelectedIndex()); 
        }
        
        public boolean isActive() {
            return !getSelectedValue().equals(ALL_VALUES);
        }
        
        public boolean acceptRow(String[] row) {
            if (isExactMatch)
                return row[column].equals(getSelectedValue());
            return row[column].indexOf(getSelectedValue()) != -1;
        }
        
        public void setChoices(String[] choices) {
            String selectedValue = null;
            if (select.getSelectedIndex() != -1)
                selectedValue = getSelectedValue();
            
            select.clear();
            select.addItem(ALL_VALUES);
            for (int i = 0; i < choices.length; i++)
                select.addItem(choices[i]);
            
            if (selectedValue != null) {
                setChoice(selectedValue);
            }
        }
        
        public void update() {
            if (!isManualChoices)
                setChoices(gatherChoices(column));
        }
        
        public void setChoice(String choice) {
            for(int i = 0; i < select.getItemCount(); i++) {
                if(select.getItemText(i).equals(choice)) {
                    select.setSelectedIndex(i);
                    return;
                }
            }
            
            select.addItem(choice);
            select.setSelectedIndex(select.getItemCount() - 1);
        }
    }
    
    class SearchFilter implements Filter {
        public int[] searchColumns;
        public TextBox searchBox = new TextBox();
        
        public SearchFilter(int[] searchColumns) {
            this.searchColumns = searchColumns;
            searchBox.setStylePrimaryName("filter-box");
        }

        public boolean acceptRow(String[] row) {
            String query = searchBox.getText();
            for (int i = 0; i < searchColumns.length; i++) {
                if (row[searchColumns[i]].indexOf(query) != -1) {
                    return true;
                }
            }
            return false;
        }

        public boolean isActive() {
            return !searchBox.getText().equals("");
        }
        
        public void update() {}
    }
    
    class SortIndicator extends Composite {
        protected Image image = new Image();
        
        public SortIndicator() {
            initWidget(image);
            setVisible(false);
        }
        
        public void sortOn(boolean up) {
            image.setUrl(up ? SORT_UP_IMAGE : SORT_DOWN_IMAGE);
            setVisible(true);
        }
        
        public void sortOff() {
            setVisible(false);
        }
    }
    
    protected List allData = new ArrayList(); // ArrayList<String[]>
    protected List filteredData = new ArrayList();
    
    protected int sortDirection = ASCENDING;
    protected boolean clientSortable = false;
    protected SortIndicator[] sortIndicators;
    protected int sortedOn = NO_COLUMN;
    
    protected Vector filters = new Vector();
    protected ColumnFilter[] columnFilters;
    protected Paginator paginator = null;
    
    protected DynamicTableListener listener;
    
    public DynamicTable(String[][] columns) {
        super(columns);
        columnFilters = new ColumnFilter[columns.length];
    }
    
    // SORTING
    
    /**
     * Makes the table client sortable, that is, sortable by the user by 
     * clicking on column headers. 
     */
    public void makeClientSortable() {
        this.clientSortable = true;
        table.getRowFormatter().addStyleName(0, DataTable.HEADER_STYLE + "-sortable");
        
        sortIndicators = new SortIndicator[columns.length];
        for(int i = 0; i < columns.length; i++) {
            sortIndicators[i] = new SortIndicator();
            
            // we have to use an HTMLPanel here to preserve styles correctly and
            // not break hover
            // we add a <span> with a unique ID to hold the sort indicator
            String name = columns[i][1];
            String id = HTMLPanel.createUniqueId();
            HTMLPanel panel = new HTMLPanel(name + 
                                            " <span id=\"" + id + "\"></span>");
            panel.add(sortIndicators[i], id);
            table.setWidget(0, i, panel);
        }
        
        table.addTableListener(new TableListener() {
            public void onCellClicked(SourcesTableEvents sender, int row, int cell) {
                if (row == headerRow) {
                    sortOnColumn(cell);
                    doAllFilters();
                }
            }
        });
    }
    
    protected Comparator getRowComparator() {
        return new Comparator() {
            public int compare(Object arg0, Object arg1) {
                String[] row0 = (String[]) arg0;
                String[] row1 = (String[]) arg1;
                return row0[sortedOn].compareTo(row1[sortedOn]) * sortDirection;
            }
        };
    }
    
    protected void sortData(List data) {
        if (sortedOn == NO_COLUMN)
            return;
        Collections.sort(data, getRowComparator());
    }
    
    /**
     * Set column on which data is sorted.  You must call <code>updateData()
     * </code> after this to display the results.
     * @param column index of the column to sort on
     */
    public void sortOnColumn(int column) {
        if (column == sortedOn)
            sortDirection *= -1;
        else
            sortDirection = ASCENDING;
        
        if(clientSortable) {
            if (sortedOn != NO_COLUMN)
                sortIndicators[sortedOn].sortOff();
            sortIndicators[column].sortOn(sortDirection == ASCENDING);
        }
        sortedOn = column;
        
        sortData(allData);
    }
    
    // PAGINATION
    
    /**
     * Add client-side pagination to this table.
     * @param rowsPerPage size of each page
     */
    public void addPaginator(int rowsPerPage) {
        paginator = new Paginator(rowsPerPage, 
                                  new Paginator.PaginatorCallback() {
            public void doRequest(int start) {
                refreshDisplay();
            }
        });
        
        addHeaderRow(paginator);
        updatePaginator();
    }
    
    protected void updatePaginator() {
        if(paginator != null)
            paginator.setNumTotalResults(filteredData.size());
    }
    
    /**
     * Reset paginator back to first page.  You must call 
     * <code>updateData()</code> after this to display the results.
     */
    public void resetPaginator() {
        if(paginator != null)
            paginator.setStart(0);
    }
    
    /**
     * Get the index of the first row currently displayed.
     */
    public int getVisibleStart() {
        return paginator.getStart();
    }
    
    /**
     * Get the number of rows currently displayed.
     */
    public int getVisibleCount() {
        return getRowCount();
    }
    
    // DATA MANIPULATION

    public void addRowFromData(String[] rowData) {
        int insertPosition = allData.size();
        if (sortedOn != NO_COLUMN) {
            insertPosition = Collections.binarySearch(allData, rowData, 
                                                      getRowComparator());
            if (insertPosition < 0)
                insertPosition = -insertPosition - 1; // see binarySearch() docs
        }
        allData.add(insertPosition, rowData);
    }

    /**
     * Remove a row from the table.
     * @param dataRow the index of the row (indexed into the table's filtered 
     * data, not into the currently visible rows)
     * @return the column data for the removed row
     */
    public String[] removeDataRow(int dataRow) {
        String[] rowText = (String[]) filteredData.remove(dataRow);
        allData.remove(rowText);
        return rowText;
    }

    public void clear() {
        super.clear();
        allData.clear();
        filteredData.clear();
    }
    
    /**
     * This method should be called after any changes to the table's data. It
     * recomputes choices for column filters, runs all filters to compute 
     * the filtered data set, and updates the display.
     */
    public void updateData() {
        updateFilters();
        doAllFilters();
    }
    
    /**
     * Get the number of rows in the currently filtered data set.
     */
    public int getFilteredRowCount() {
        return filteredData.size();
    }
    
    /**
     * Get a row in the currently filtered data set.
     * @param dataRow the index (into the filtered data set) of the row to 
     * retrieve
     * @return the column data for the row
     */
    public String[] getDataRow(int dataRow) {
        return (String[]) filteredData.get(dataRow);
    }
    
    // DISPLAY
    
    protected void displayRows(List rows, int start, int end) {
        super.clear();
        for (int i = start; i < end; i++) {
            super.addRowFromData((String[]) rows.get(i));
        }
    }
    
    protected void displayRows(List rows) {
        displayRows(rows, 0, rows.size());
    }
    
    /**
     * Update the table display.
     */
    public void refreshDisplay() {
        if(paginator != null)
            displayRows(filteredData, paginator.getStart(), paginator.getEnd());
        else
            displayRows(filteredData);
    }
    
    // INPUT
    
    protected int visibleRowToFilteredDataRow(int visibleRow) {
        if (visibleRow <= headerRow)
            return -1;
        
        int start = 0;
        if (paginator != null)
            start = paginator.getStart();
        return visibleRow - getHeaderRowCount() + start;
    }
    
    /**
     * Set a DynamicTableListener.  This differs from a normal TableListener 
     * because the row index passed is an index into the filtered data set, 
     * rather than an index into the visible table, which would be relatively 
     * useless.
     */
    public void setListener(final DynamicTableListener listener) {
        table.addTableListener(new TableListener() {
            public void onCellClicked(SourcesTableEvents sender, int row, int cell) {
                int dataRow = visibleRowToFilteredDataRow(row);
                if (dataRow != -1)
                    listener.onRowClicked(dataRow, cell);
            }
        });
    }
    
    // FILTERING
    
    protected List getActiveFilters() {
        List activeFilters = new ArrayList();
        for (Iterator i = filters.iterator(); i.hasNext(); ) {
            Filter filter = (Filter) i.next();
            if (filter.isActive())
                activeFilters.add(filter);
        }
        return activeFilters;
    }
    
    protected boolean acceptRow(String[] row, List filters) {
        for (Iterator i = filters.iterator(); i.hasNext(); ) {
            Filter filter = (Filter) i.next();
            if(!filter.acceptRow(row)) {
                return false;
            }
        }
        return true;
    }
    
    protected void doAllFilters() {
        filteredData.clear();
        List activeFilters = getActiveFilters();
        for (Iterator i = allData.iterator(); i.hasNext(); ) {
            String[] row = (String[]) i.next();
            if (acceptRow(row, activeFilters))
                filteredData.add(row);
        }
        
        updatePaginator();
        refreshDisplay();
    }
    
    protected int columnNameToIndex(String column) {
        for(int col = 0; col < columns.length; col++) {
            if (columns[col][1].equals(column))
                    return col;
        }
        
        return -1;
    }
    
    /**
     * Add an incremental search filter.  This appears as a text box which 
     * performs a substring search on the given columns.
     * @param searchColumns the titles of columns to perform the search on.
     */
    public void addSearchBox(String[] searchColumns, String label) {
        int[] searchColumnIndices = new int[searchColumns.length];
        for(int i = 0; i < searchColumns.length; i++) {
            searchColumnIndices[i] = columnNameToIndex(searchColumns[i]);
        }
        SearchFilter searchFilter = new SearchFilter(searchColumnIndices);
        filters.add(searchFilter);
        
        final HorizontalPanel searchPanel = new HorizontalPanel();
        final Label searchLabel = new Label(label);
        searchPanel.add(searchLabel);
        searchPanel.add(searchFilter.searchBox);
        addHeaderRow(searchPanel);
        searchFilter.searchBox.addKeyboardListener(new KeyboardListener() {
            public void onKeyPress(Widget sender, char keyCode, int modifiers) {}
            public void onKeyDown(Widget sender, char keyCode, int modifiers) {}
            public void onKeyUp(Widget sender, char keyCode, int modifiers) {
                doAllFilters();
            }
        });
    }
    
    protected String[] gatherChoices(int column) {
        Set choices = new HashSet();
        for(Iterator i = allData.iterator(); i.hasNext(); ) {
            String[] row = (String[]) i.next();
            choices.add(row[column]);
        }
        
        if (choices.isEmpty())
            return new String[0];
        List sortedChoices = new ArrayList(choices);
        Collections.sort(sortedChoices);
        return (String[]) sortedChoices.toArray(new String[1]);
    }
    
    /**
     * Add a column filter.  This presents choices for the value of the given
     * column in a list box, and filters based on the user's choice.  This
     * method allows the caller to specify the choices for the list box.
     * @param column the title of the column to filter on
     * @param choices the choices for the filter box (not including "All values")
     * @param exactMatch if true, the column value must match exactly; otherwise,
     *        it must contain the filter value
     */
    public void addColumnFilter(String column, String[] choices,
                                boolean exactMatch) {
        final ColumnFilter filter = new ColumnFilter(columnNameToIndex(column));
        if (choices != null) {
            filter.setChoices(choices);
            filter.isManualChoices = true;
        }
        filter.setExactMatch(exactMatch);
        filter.select.addChangeListener(new ChangeListener() {
            public void onChange(Widget sender) {
                doAllFilters();
            }
        });
        filters.add(filter);
        columnFilters[columnNameToIndex(column)] = filter;
        
        Label filterLabel = new Label(column + ":");
        HorizontalPanel filterPanel = new HorizontalPanel();
        filterPanel.add(filterLabel);
        filterPanel.add(filter.select);
        
        addHeaderRow(filterPanel);
    }
    
    /**
     * Add a column filter without specifying choices.  Choices will 
     * automatically be determined by gathering all values for the given column
     * present in the table.
     */
    public void addColumnFilter(String column) {
        addColumnFilter(column, null, true);
    }
    
    /**
     * Set the selected choice for the column filter of the given column.
     * @param columnName title of the column for which the filter should be set
     * @param choice value to select in the filter
     */
    public void setColumnFilterChoice(String columnName, String choice) {
        int column = columnNameToIndex(columnName);
        ColumnFilter filter = columnFilters[column];
        if (filter == null)
            throw new IllegalArgumentException(
                                           "No filter on column " + columnName);
        filter.setChoice(choice);
    }
    
    protected void updateFilters() {
        for(Iterator i = filters.iterator(); i.hasNext(); ) {
            Filter filter = (Filter) i.next();
            filter.update();
        }
    }
}
