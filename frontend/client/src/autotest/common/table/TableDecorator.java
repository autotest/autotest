package autotest.common.table;

import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.ui.Paginator;
import autotest.common.ui.TableActionsPanel;
import autotest.common.ui.TableSelectionPanel;
import autotest.common.ui.TableActionsPanel.TableActionsListener;
import autotest.common.ui.TableActionsPanel.TableActionsWithExportCsvListener;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.Widget;

/**
 * This class can optionally add any of the following controls around a table (in this order of 
 * layout): 
 * Filter controls
 * Selection/action menu
 * Top paginator
 * Actual data table
 * Bottom paginator
 */
public class TableDecorator extends Composite implements DynamicTableListener {
    private FlexTable enclosingTable = new FlexTable();
    private FlexTable filterTable = new FlexTable();
    private DynamicTable dataTable;
    private SelectionManager selectionManager;
    private int numFilters = 0;
    
    private static class LayoutRows {
        public static final int FILTERS = 0,
                                ACTIONS = 1,
                                TOP_PAGINATOR = 2,
                                TABLE = 3,
                                BOTTOM_PAGINATOR = 4;
    }
    
    public TableDecorator(DynamicTable dataTable) {
        this.dataTable = dataTable;
        setRow(LayoutRows.TABLE, dataTable);
        setRow(LayoutRows.FILTERS, filterTable);
        initWidget(enclosingTable);
    }
    
    public void addPaginators() {
        for(int i = 0; i < 2; i++) {
            Paginator p = new Paginator();
            dataTable.attachPaginator(p);
            if (i == 0) { // add at top
                setRow(LayoutRows.TOP_PAGINATOR, p);
            }
            else { // add at bottom
                setRow(LayoutRows.BOTTOM_PAGINATOR, p);
            }
        }
    }
    
    public void addFilter(String text, Filter filter) {
        dataTable.addFilter(filter);
        addControl(text, filter.getWidget());
    }
    
    public void addControl(String text, Widget widget) {
      int row = numFilters;
      numFilters++;
      filterTable.setText(row, 0, text);
      filterTable.setWidget(row, 1, widget);
    }
    
    public SelectionManager addSelectionManager(boolean selectOnlyOne) {
        selectionManager = new DynamicTableSelectionManager(dataTable, selectOnlyOne);
        dataTable.addListener(this);
        return selectionManager;
    }
    
    public void addSelectionPanel(boolean wantSelectVisible) {
        assert selectionManager != null;
        TableSelectionPanel selectionPanel = new TableSelectionPanel(wantSelectVisible);
        selectionPanel.setListener(selectionManager);
        setActionsWidget(selectionPanel);
    }

    private TableActionsPanel createTableActionsPanel(boolean wantSelectVisible) {
        assert selectionManager != null;
        TableActionsPanel actionsPanel = new TableActionsPanel(wantSelectVisible);
        actionsPanel.setSelectionListener(selectionManager);
        return actionsPanel;
    }

    public void addTableActionsPanel(TableActionsListener listener, boolean wantSelectVisible) {
        TableActionsPanel actionsPanel = createTableActionsPanel(wantSelectVisible);
        actionsPanel.setActionsListener(listener);
        setActionsWidget(actionsPanel);
    }

    public void addTableActionsWithExportCsvListener(TableActionsWithExportCsvListener listener) {
        TableActionsPanel actionsPanel = createTableActionsPanel(true);
        actionsPanel.setActionsWithCsvListener(listener);
        setActionsWidget(actionsPanel);
    }

    public void setActionsWidget(Widget widget) {
        setRow(LayoutRows.ACTIONS, widget);
    }

    private void setRow(int row, Widget widget) {
        enclosingTable.setWidget(row, 0, widget);
    }

    public void onRowClicked(int rowIndex, JSONObject row) {}

    public void onTableRefreshed() {
        assert selectionManager != null;
        selectionManager.refreshSelection();
    }
}
