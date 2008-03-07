package afeclient.client;

import java.util.ArrayList;
import java.util.List;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

/**
 * A widget to facilitate selection of a group of hosts for running a job.  The
 * widget displays two side-by-side tables; the left table is a normal 
 * {@link HostTable} displaying available, unselected hosts, and the right table 
 * displays selected hosts.  Click on a host in either table moves it to the 
 * other (i.e. selects or deselects a host).  The widget provides several 
 * convenience controls (such as one to remove all selected hosts) and a special
 * section for adding meta-host entries.
 */
public class HostSelector {
    public static final int TABLE_SIZE = 10;
    public static final String META_PREFIX = "Any ";
    
    class HostSelection {
        public List hosts = new ArrayList();
        public List metaHosts = new ArrayList();
    }
    
    protected HostTable availableTable = new HostTable(TABLE_SIZE);
    protected DynamicTable selectedTable = 
        new DynamicTable(HostTable.HOST_COLUMNS);
    
    public HostSelector() {
        selectedTable.setClickable(true);
        selectedTable.addPaginator(TABLE_SIZE);
        selectedTable.sortOnColumn(0);
        
        availableTable.setClickable(true);
        availableTable.setColumnFilterChoice("Locked", "No");
        availableTable.getHosts();
        
        availableTable.setListener(new DynamicTable.DynamicTableListener() {
            public void onRowClicked(int dataRow, int column) {
                selectRow(dataRow);
            }
        });
        selectedTable.setListener(new DynamicTable.DynamicTableListener() {
            public void onRowClicked(int dataRow, int column) {
                deselectRow(dataRow);
            }
        });
        
        RootPanel.get("create_available_table").add(availableTable);
        RootPanel.get("create_selected_table").add(selectedTable);
        
        Button addVisibleButton = new Button("Add currently displayed");
        addVisibleButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                addVisible();
            }
        });
        Button addFilteredButton = new Button("Add all filtered");
        addFilteredButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                moveAll(availableTable, selectedTable);
            }
        });
        Button removeAllButton = new Button("Remove all");
        removeAllButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                moveAll(selectedTable, availableTable);
            }
        });
        
        Panel availableControls = new HorizontalPanel();
        availableControls.add(addVisibleButton);
        availableControls.add(addFilteredButton);
        RootPanel.get("create_available_controls").add(availableControls);
        RootPanel.get("create_selected_controls").add(removeAllButton);
        
        final ListBox metaLabelSelect = new ListBox();
        populateLabels(metaLabelSelect);
        final TextBox metaNumber = new TextBox();
        metaNumber.setVisibleLength(4);
        final Button metaButton = new Button("Add");
        metaButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                int selected = metaLabelSelect.getSelectedIndex();
                String label = metaLabelSelect.getItemText(selected);
                String number = metaNumber.getText();
                try {
                    Integer.parseInt(number);
                }
                catch (NumberFormatException exc) {
                    String error = "Invalid number " + number;
                    NotifyManager.getInstance().showError(error);
                    return;
                }
                String[] rowData = new String[4];
                rowData[0] = META_PREFIX + number;
                rowData[1] = label;
                rowData[2] = rowData[3] = "";
                selectedTable.addRowFromData(rowData);
                selectedTable.updateData();
            }
        });
        RootPanel.get("create_meta_select").add(metaLabelSelect);
        RootPanel.get("create_meta_number").add(metaNumber);
        RootPanel.get("create_meta_button").add(metaButton);
    }
    
    protected void moveRow(int row, DynamicTable from, DataTable to) {
        String[] rowData = from.removeDataRow(row);
        if(isMetaEntry(rowData))
            return;
        to.addRowFromData(rowData);
    }
    
    protected void updateAfterMove(DynamicTable from, DynamicTable to) {
        from.updateData();
        to.updateData();
    }
    
    protected void selectRow(int row) {
        moveRow(row, availableTable, selectedTable);
        updateAfterMove(availableTable, selectedTable);
    }
    
    protected void deselectRow(int row) {
        moveRow(row, selectedTable, availableTable);
        updateAfterMove(selectedTable, availableTable);
    }
    
    protected void addVisible() {
        int start = availableTable.getVisibleStart();
        int count = availableTable.getVisibleCount();
        for (int i = 0; i < count; i++) {
            moveRow(start, availableTable, selectedTable);
        }
        updateAfterMove(availableTable, selectedTable);
    }
    
    protected void moveAll(DynamicTable from, DynamicTable to) {
        int total = from.getFilteredRowCount();
        for (int i = 0; i < total; i++) {
            moveRow(0, from, to);
        }
        updateAfterMove(from, to);
    }
    
    protected void populateLabels(ListBox list) {
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray labels = staticData.getData("labels").isArray();
        for(int i = 0; i < labels.size(); i++) {
            list.addItem(labels.get(i).isString().stringValue());
        }
    }
    
    protected boolean isMetaEntry(String[] row) {
        return row[0].startsWith(META_PREFIX);
    }
    
    protected int getMetaNumber(String[] row) {
        return Integer.parseInt(row[0].substring(META_PREFIX.length()));
    }
    
    /**
     * Retrieve the set of selected hosts.
     */
    public HostSelection getSelectedHosts() {
        HostSelection selection = new HostSelection();
        for(int i = 0; i < selectedTable.getFilteredRowCount(); i++) {
            String[] row = selectedTable.getDataRow(i);
            if (isMetaEntry(row)) {
                int count =  getMetaNumber(row);
                String platform = row[1];
                for(int counter = 0; counter < count; counter++) {
                    selection.metaHosts.add(platform);
                }
            }
            else {
                String hostname = row[0];
                selection.hosts.add(hostname);
            }
        }
        
        return selection;
    }
    
    /**
     * Reset the widget (deselect all hosts).
     */
    public void reset() {
        moveAll(selectedTable, availableTable);
    }
}
