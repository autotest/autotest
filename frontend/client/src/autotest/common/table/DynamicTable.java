package autotest.common.table;

import autotest.common.SimpleCallback;
import autotest.common.table.DataSource.DataCallback;
import autotest.common.table.DataSource.SortDirection;
import autotest.common.table.DataSource.SortSpec;
import autotest.common.ui.Paginator;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.Image;
import com.google.gwt.user.client.ui.SourcesTableEvents;
import com.google.gwt.user.client.ui.TableListener;

import java.util.ArrayList;
import java.util.Collections;
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
    
    public static interface DynamicTableListener extends DataTableListener {
        public void onTableRefreshed();
    }
    
    static class SortIndicator extends Composite {
        public int column;
        private Image image = new Image();
        
        public SortIndicator(int column) {
            this.column = column;
            initWidget(image);
            setVisible(false);
        }
        
        public void sortOn(SortDirection direction) {
            image.setUrl(direction == SortDirection.ASCENDING ? SORT_UP_IMAGE : SORT_DOWN_IMAGE);
            setVisible(true);
        }
        
        public void sortOff() {
            setVisible(false);
        }
    }
    
    protected DataSource dataSource;
    
    private boolean clientSortable = false;
    private SortIndicator[] sortIndicators;
    private List<SortSpec> sortColumns = new ArrayList<SortSpec>();
    
    protected List<Filter> filters = new ArrayList<Filter>();
    protected List<Paginator> paginators = new ArrayList<Paginator>();
    protected Integer rowsPerPage;
    
    protected List<DynamicTableListener> dynamicTableListeners = 
        new ArrayList<DynamicTableListener>();
    
    public DynamicTable(String[][] columns, DataSource dataSource) {
        super(columns);
        setDataSource(dataSource);
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
            sortIndicators[i] = new SortIndicator(i);
            
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
    
    private void updateSortIndicators() {
        if (!clientSortable) {
            return;
        }
        
        SortSpec firstSpec = getFirstSortSpec();
        for (SortIndicator indicator : sortIndicators) {
            if (columns[indicator.column][COL_NAME].equals(firstSpec.getField())) {
                indicator.sortOn(firstSpec.getDirection());
            } else {
                indicator.sortOff();
            }
        }
    }

    private SortSpec getFirstSortSpec() {
        if (sortColumns.isEmpty()) {
            return null;
        }
        return sortColumns.get(0);
    }
    
    /**
     * Set column on which data is sorted.  You must call <code>refresh()</code>
     * after this to display the results.
     * @param columnField field of the column to sort on
     * @param sortDirection DynamicTable.ASCENDING or DynamicTable.DESCENDING
     */
    public void sortOnColumn(String columnField, SortDirection sortDirection) {
        // remove any existing sort on this column
        for (Iterator<SortSpec> i = sortColumns.iterator(); i.hasNext(); ) {
            if (i.next().getField().equals(columnField)) {
                i.remove();
                break;
            }
        }
        
        sortColumns.add(0, new SortSpec(columnField, sortDirection));
        updateSortIndicators();
    }
    
    /**
     * Defaults to ascending order.
     */
    public void sortOnColumn(String columnField) {
        sortOnColumn(columnField, SortDirection.ASCENDING);
    }
    
    public void clearSorts() {
        sortColumns.clear();
        updateSortIndicators();
    }
    
    // PAGINATION
    
    /**
     * Attach a new paginator to this table.
     */
    public void attachPaginator(Paginator paginator) {
        assert rowsPerPage != null;
        paginators.add(paginator);
        paginator.addCallback(new SimpleCallback() {
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
        this.rowsPerPage = Integer.valueOf(rowsPerPage);
        for (Paginator paginator : paginators) {
            paginator.setResultsPerPage(rowsPerPage);
        }
    }
    
    /**
     * Set start row for pagination.  You must call 
     * <code>refresh()</code> after this to display the results.
     */
    public void setPaginatorStart(int start) {
        for (Paginator paginator : paginators) {
            paginator.setStart(start);
        }
    }
    
    protected void refreshPaginators() {
        for (Paginator paginator : paginators) {
            paginator.update();
        }
    }
    
    protected void updatePaginatorTotalResults(int totalResults) {
        for (Paginator paginator : paginators) {
            paginator.setNumTotalResults(totalResults);
        }
    }
    
    
    // FILTERING
    
    public void addFilter(Filter filter) {
        filters.add(filter);
        filter.addCallback(new SimpleCallback() {
            public void doCallback(Object source) {
                setPaginatorStart(0);
                refresh();
            }
        });
    }
    
    protected void addFilterParams(JSONObject params) {
        for (Filter filter : filters) {
            if (filter.isActive()) {
                filter.addParams(params);
            }
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
        SortSpec[] sortOn = null;
        if (!paginators.isEmpty()) {
            updatePaginatorTotalResults(totalCount);
            Paginator p = paginators.get(0);
            start = Integer.valueOf(p.getStart());
            limit = Integer.valueOf(p.getResultsPerPage());
        }
        
        if (!sortColumns.isEmpty()) {
            sortOn = new SortSpec[sortColumns.size()];
            sortColumns.toArray(sortOn);
        }
        dataSource.getPage(start, limit, sortOn, this); 
    }

    public void handlePage(JSONArray data) {
        clear();
        addRows(data);
        refreshPaginators();
        notifyListenersRefreshed();
    }
    
    public String[] getRowData(int row) {
        String[] data = new String[columns.length];
        for (int i = 0; i < columns.length; i++) {
            if(isWidgetColumn(i))
                continue;
            data[i] = table.getHTML(row, i);
        }
        return data;
    }
    
    public DataSource getDataSource() {
        return dataSource;
    }
    
    public void setDataSource(DataSource dataSource) {
        this.dataSource = dataSource;
    }
    
    
    // INPUT
    
    @Override
    public void onCellClicked(SourcesTableEvents sender, int row, int cell) {
        if (clientSortable && row == headerRow) {
            if (isWidgetColumn(cell)) {
                // ignore sorting on widget columns
                return;
            }
            String columnName = columns[cell][COL_NAME];
            SortDirection newSortDirection = SortDirection.ASCENDING;
            SortSpec firstSortSpec = getFirstSortSpec();
            // when clicking on the last sorted field, invert the sort
            if (firstSortSpec != null && columnName.equals(firstSortSpec.getField())) {
                newSortDirection = invertSortDirection(firstSortSpec.getDirection());
            }
            
            sortOnColumn(columnName, newSortDirection);
            refresh();
            return;
        }
        
        super.onCellClicked(sender, row, cell);
    }
    
    private SortDirection invertSortDirection(SortDirection direction) {
        return direction == SortDirection.ASCENDING ? 
                                        SortDirection.DESCENDING : SortDirection.ASCENDING;
    }

    public void addListener(DynamicTableListener listener) {
        super.addListener(listener);
        dynamicTableListeners.add(listener);
    }
    
    public void removeListener(DynamicTableListener listener) {
        super.removeListener(listener);
        dynamicTableListeners.remove(listener);
    }
    
    protected void notifyListenersRefreshed() {
        for (DynamicTableListener listener : dynamicTableListeners) {
            listener.onTableRefreshed();
        }
    }
    
    public List<SortSpec> getSortSpecs() {
        return Collections.unmodifiableList(sortColumns);
    }

    public void onError(JSONObject errorObject) {
        // nothing to do
    }
}
