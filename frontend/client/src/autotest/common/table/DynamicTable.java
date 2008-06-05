package afeclient.client.table;

import afeclient.client.Paginator;
import afeclient.client.SimpleCallback;
import afeclient.client.table.DataSource.DataCallback;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.Image;
import com.google.gwt.user.client.ui.SourcesTableEvents;
import com.google.gwt.user.client.ui.TableListener;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 * Extended DataTable supporting sorting, filtering and pagination.
 */
public class DynamicTable extends DataTable 
                          implements DataCallback, TableListener {
    public static final int NO_COLUMN = -1;
    public static final String SORT_UP_IMAGE = "arrow_up.png",
                               SORT_DOWN_IMAGE = "arrow_down.png";
    
    public interface DynamicTableListener {
        public void onRowClicked(int rowIndex, JSONObject row);
        public void onTableRefreshed();
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
    
    protected DataSource dataSource;
    
    protected int sortDirection = DataSource.ASCENDING;
    protected boolean clientSortable = false;
    protected SortIndicator[] sortIndicators;
    protected int sortedOn = NO_COLUMN;
    
    protected List filters = new ArrayList();
    protected List paginators = new ArrayList();
    protected Integer rowsPerPage;
    
    protected List listeners = new ArrayList();
    
    public DynamicTable(String[][] columns, DataSource dataSource) {
        super(columns);
        this.dataSource = dataSource;
        table.addTableListener(this);
    }
    
    // SORTING
    
    /**
     * Makes the table client sortable, that is, sortable by the user by 
     * clicking on column headers. 
     */
    public void makeClientSortable() {
        this.clientSortable = true;
        table.getRowFormatter().addStyleName(0, 
                                         DataTable.HEADER_STYLE + "-sortable");
        
        sortIndicators = new SortIndicator[columns.length];
        for(int i = 0; i < columns.length; i++) {
            sortIndicators[i] = new SortIndicator();
            
            // we have to use an HTMLPanel here to preserve styles correctly and
            // not break hover
            // we add a <span> with a unique ID to hold the sort indicator
            String name = columns[i][COL_TITLE];
            String id = HTMLPanel.createUniqueId();
            HTMLPanel panel = new HTMLPanel(name + 
                                            " <span id=\"" + id + "\"></span>");
            panel.add(sortIndicators[i], id);
            table.setWidget(0, i, panel);
        }
    }
    
    protected void sortOnColumnIndex(int column, int sortDirection) {
        this.sortDirection = sortDirection;
        
        if(clientSortable) {
            if (sortedOn != NO_COLUMN)
                sortIndicators[sortedOn].sortOff();
            sortIndicators[column].sortOn(sortDirection == DataSource.ASCENDING);
        }
        sortedOn = column;
    }
    
    /**
     * Set column on which data is sorted.  You must call <code>refresh()</code>
     * after this to display the results.
     * @param columnName name of the column to sort on
     * @param sortDirection DynamicTable.ASCENDING or DynamicTable.DESCENDING
     */
    public void sortOnColumn(String columnName, int sortDirection) {
        sortOnColumnIndex(columnNameToIndex(columnName), sortDirection);
        
    }
    
    /**
     * Defaults to ascending order.
     */
    public void sortOnColumn(String columnName) {
        sortOnColumn(columnName, DataSource.ASCENDING);
    }
    
    // PAGINATION
    
    /**
     * Attach a new paginator to this table.
     */
    public void attachPaginator(Paginator paginator) {
        assert rowsPerPage != null;
        paginators.add(paginator);
        paginator.addChangeListener(new SimpleCallback() {
            public void doCallback(Object source) {
                setPaginatorStart(((Paginator) source).getStart());
                refresh();
            } 
        });
        paginator.setResultsPerPage(rowsPerPage.intValue());
    }
    
    /**
     * Set the page size of this table (only useful if you attach paginators).
     */
    public void setRowsPerPage(int rowsPerPage) {
        assert rowsPerPage > 0;
        this.rowsPerPage = new Integer(rowsPerPage);
        for (Iterator i = paginators.iterator(); i.hasNext(); ) {
            ((Paginator) i.next()).setResultsPerPage(rowsPerPage);
        }
    }
    
    /**
     * Set start row for pagination.  You must call 
     * <code>refresh()</code> after this to display the results.
     */
    public void setPaginatorStart(int start) {
        for (Iterator i = paginators.iterator(); i.hasNext(); ) {
            ((Paginator) i.next()).setStart(start);
        }
    }
    
    protected void refreshPaginators() {
        for (Iterator i = paginators.iterator(); i.hasNext(); ) {
            ((Paginator) i.next()).update();
        }
    }
    
    protected void updatePaginatorTotalResults(int totalResults) {
        for (Iterator i = paginators.iterator(); i.hasNext(); ) {
            ((Paginator) i.next()).setNumTotalResults(totalResults);
        }
    }
    
    
    // FILTERING
    
    public void addFilter(Filter filter) {
        filters.add(filter);
        filter.addListener(new SimpleCallback() {
            public void doCallback(Object source) {
                setPaginatorStart(0);
                refresh();
            }
        });
    }
    
    protected void addFilterParams(JSONObject params) {
        for (Iterator i = filters.iterator(); i.hasNext(); ) {
            Filter filter = (Filter) i.next();
            if (filter.isActive())
                filter.addParams(params);
        }
    }
    
    
    // DATA MANAGEMENT
    
    public void refresh() {
        JSONObject params = new JSONObject();
        addFilterParams(params);
        dataSource.updateData(params, this);
    }
    
    public void onGotData(int totalCount) {
        Integer start = null, limit = null;
        String sortOn = null;
        if (!paginators.isEmpty()) {
            updatePaginatorTotalResults(totalCount);
            Paginator p = (Paginator) paginators.get(0);
            start = new Integer(p.getStart());
            limit = new Integer(p.getResultsPerPage());
        }
        if (sortedOn != NO_COLUMN)
            sortOn = columns[sortedOn][COL_NAME];
        dataSource.getPage(start, limit, sortOn, new Integer(sortDirection),
                           this); 
    }

    public void handlePage(JSONArray data) {
        clear();
        addRows(data);
        refreshPaginators();
        notifyListenersRefreshed();
    }
    
    public String[] getRowData(int row) {
        String[] data = new String[columns.length];
        for (int i = 0; i < columns.length; i++)
            data[i] = table.getHTML(row, i);
        return data;
    }
    
    public DataSource getDataSource() {
        return dataSource;
    }
    
    
    // INPUT
    
    public void onCellClicked(SourcesTableEvents sender, int row, int cell) {
        if (clientSortable && row == headerRow) {
            int newSortDirection = DataSource.ASCENDING;
            if (cell == sortedOn)
                newSortDirection = sortDirection * -1;
            sortOnColumnIndex(cell, newSortDirection);
            refresh();
        }
        
        if (row != headerRow)
            notifyListenersClicked(row - headerRow - 1);
    }
    
    public void addListener(DynamicTableListener listener) {
        listeners.add(listener);
    }
    
    public void removeListener(DynamicTableListener listener) {
        listeners.remove(listener);
    }
    
    protected void notifyListenersClicked(int rowIndex) {
        JSONObject row = getRow(rowIndex);
        for (Iterator i = listeners.iterator(); i.hasNext(); )
            ((DynamicTableListener) i.next()).onRowClicked(rowIndex, row);
    }
    
    protected void notifyListenersRefreshed() {
        for (Iterator i = listeners.iterator(); i.hasNext(); )
            ((DynamicTableListener) i.next()).onTableRefreshed();
    }
    
    // OTHER

    protected int columnNameToIndex(String column) {
        for(int col = 0; col < columns.length; col++) {
            if (columns[col][COL_TITLE].equals(column))
                    return col;
        }
        
        throw new IllegalArgumentException("Nonexistent column");
    }
}
