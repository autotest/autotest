package afeclient.client;

import afeclient.client.table.ArrayDataSource;
import afeclient.client.table.DataSource;
import afeclient.client.table.SelectionManager;
import afeclient.client.table.TableDecorator;
import afeclient.client.table.DataSource.DefaultDataCallback;
import afeclient.client.table.DynamicTable.DynamicTableListener;
import afeclient.client.table.SelectionManager.SelectionListener;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Iterator;
import java.util.List;

/**
 * A widget to facilitate selection of a group of hosts for running a job.  The
 * widget displays two side-by-side tables; the left table is a normal 
 * {@link RpcHostTable} displaying available, unselected hosts, and the right table 
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
    
    protected ArrayDataSource selectedHostData = new ArrayDataSource("hostname");
    
    protected HostTable availableTable = new RpcHostTable();
    protected HostTableDecorator availableDecorator = 
        new HostTableDecorator(availableTable, TABLE_SIZE);
    protected HostTable selectedTable = new HostTable(selectedHostData);
    protected TableDecorator selectedDecorator = 
        new TableDecorator(selectedTable);
    
    protected SelectionManager availableSelection = 
        new SelectionManager(availableTable, false);
    
    public HostSelector() {
        selectedTable.setClickable(true);
        selectedTable.setRowsPerPage(TABLE_SIZE);
        selectedDecorator.addPaginators();
        
        availableTable.setClickable(true);
        availableDecorator.lockedFilter.setSelectedChoice("No");
        
        availableSelection.addListener(new SelectionListener() {
            public void onAdd(Collection objects) {
                for (Iterator i = objects.iterator(); i.hasNext(); )
                    selectRow((JSONObject) i.next());
                selectionRefresh();
            }

            public void onRemove(Collection objects) {
                for (Iterator i = objects.iterator(); i.hasNext(); )
                    deselectRow((JSONObject) i.next());
                selectionRefresh();
            }
        });

        selectedTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                deselectRow(row);
                selectionRefresh();
            }
            
            public void onTableRefreshed() {}
        });
        
        RootPanel.get("create_available_table").add(availableDecorator);
        RootPanel.get("create_selected_table").add(selectedDecorator);
        
        Button addVisibleButton = new Button("Select visible");
        addVisibleButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                addVisible();
            }
        });
        Button addFilteredButton = new Button("Select all");
        addFilteredButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                addAllFiltered();
            }
        });
        Button removeAllButton = new Button("Select none");
        removeAllButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                deselectAll();
            }
        });
        
        Panel availableControls = new HorizontalPanel();
        availableControls.add(addVisibleButton);
        availableControls.add(addFilteredButton);
        availableControls.add(removeAllButton);
        RootPanel.get("create_available_controls").add(availableControls);
        
        final ListBox metaLabelSelect = new ListBox();
        populateLabels(metaLabelSelect);
        final TextBox metaNumber = new TextBox();
        metaNumber.setVisibleLength(4);
        final Button metaButton = new Button("Add");
        metaButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                int selected = metaLabelSelect.getSelectedIndex();
                String labelName = metaLabelSelect.getItemText(selected);
                String label = Utils.decodeLabelName(labelName);
                String number = metaNumber.getText();
                try {
                    Integer.parseInt(number);
                }
                catch (NumberFormatException exc) {
                    String error = "Invalid number " + number;
                    NotifyManager.getInstance().showError(error);
                    return;
                }
                
                JSONObject metaObject = new JSONObject();
                metaObject.put("hostname", new JSONString(META_PREFIX + number));
                metaObject.put("platform", new JSONString(label));
                metaObject.put("labels", new JSONArray());
                metaObject.put("status", new JSONString(""));
                metaObject.put("locked", new JSONNumber(0));
                selectRow(metaObject);
                selectionRefresh();
            }
        });
        RootPanel.get("create_meta_select").add(metaLabelSelect);
        RootPanel.get("create_meta_number").add(metaNumber);
        RootPanel.get("create_meta_button").add(metaButton);
    }
    
    protected void selectRow(JSONObject row) {
        selectedHostData.addItem(row);
    }
    
    protected void deselectRow(JSONObject row) {
        selectedHostData.removeItem(row);
    }
    
    protected void addVisible() {
        List rowsToAdd = new ArrayList();
        for (int i = 0; i < availableTable.getRowCount(); i++) {
            rowsToAdd.add(availableTable.getRow(i));
        }
        availableSelection.selectObjects(rowsToAdd);
    }
    
    protected void addAllFiltered() {
        DataSource availableDataSource = availableTable.getDataSource();
        availableDataSource.getPage(null, null, null, null, 
                                    new DefaultDataCallback() {
            public void handlePage(JSONArray data) {
                availableSelection.selectObjects(new JSONArrayList(data));
            }
        });
    }
    
    protected void deselectAll() {
        availableSelection.deselectAll();
        // get rid of leftover meta-host entries
        selectedHostData.clear();
    }
    
    protected void populateLabels(ListBox list) {
        String[] labelNames = Utils.getLabelStrings();
        for(int i = 0; i < labelNames.length; i++) {
            list.addItem(labelNames[i]);
        }
    }
    
    protected String getHostname(JSONObject row) {
        return row.get("hostname").isString().stringValue();
    }
    
    protected boolean isMetaEntry(JSONObject row) {
        return getHostname(row).startsWith(META_PREFIX);
    }
    
    protected int getMetaNumber(JSONObject row) {
        return Integer.parseInt(getHostname(row).substring(META_PREFIX.length()));
    }
    
    /**
     * Retrieve the set of selected hosts.
     */
    public HostSelection getSelectedHosts() {
        HostSelection selection = new HostSelection();
        List selectionArray = selectedHostData.getItems();
        for(Iterator i = selectionArray.iterator(); i.hasNext(); ) {
            JSONObject row = (JSONObject) i.next();
            if (isMetaEntry(row)) {
                int count =  getMetaNumber(row);
                String platform = row.get("platform").isString().stringValue();
                for(int counter = 0; counter < count; counter++) {
                    selection.metaHosts.add(platform);
                }
            }
            else {
                String hostname = getHostname(row);
                selection.hosts.add(hostname);
            }
        }
        
        return selection;
    }
    
    /**
     * Reset the widget (deselect all hosts).
     */
    public void reset() {
        deselectAll();
        selectionRefresh();
    }
    
    /**
     * Refresh as necessary for selection change, but don't make any RPCs.
     */
    protected void selectionRefresh() {
        selectedTable.refresh();
        availableSelection.refreshSelection();
    }
    
    public void refresh() {
        availableTable.refresh();
        selectionRefresh();
    }
}
