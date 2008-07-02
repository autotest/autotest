package autotest.afe;

import autotest.common.JSONArrayList;
import autotest.common.table.ArrayDataSource;
import autotest.common.table.DataSource;
import autotest.common.table.SelectionManager;
import autotest.common.table.TableDecorator;
import autotest.common.table.DataSource.DefaultDataCallback;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.table.SelectionManager.SelectionListener;
import autotest.common.ui.NotifyManager;

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
    
    static class HostSelection {
        public List<String> hosts = new ArrayList<String>();
        public List<String> metaHosts = new ArrayList<String>();
    }
    
    protected ArrayDataSource<JSONObject> selectedHostData =
        new ArrayDataSource<JSONObject>("hostname");
    
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
            public void onAdd(Collection<JSONObject> objects) {
                for (JSONObject row : objects) {
                    selectRow(row);
                }
                selectionRefresh();
            }

            public void onRemove(Collection<JSONObject> objects) {
                for (JSONObject row : objects) {
                    deselectRow(row);
                }
                selectionRefresh();
            }
        });

        selectedTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                if (isMetaEntry(row)) {
                    deselectRow(row);
                    selectionRefresh();
                }
                else
                    availableSelection.deselectObject(row);
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
                String label = AfeUtils.decodeLabelName(labelName);
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
        List<JSONObject> rowsToAdd = new ArrayList<JSONObject>();
        for (int i = 0; i < availableTable.getRowCount(); i++) {
            rowsToAdd.add(availableTable.getRow(i));
        }
        availableSelection.selectObjects(rowsToAdd);
    }
    
    protected void addAllFiltered() {
        DataSource availableDataSource = availableTable.getDataSource();
        availableDataSource.getPage(null, null, null, null, 
                                    new DefaultDataCallback() {
            @Override
            public void handlePage(JSONArray data) {
                availableSelection.selectObjects(
                    new JSONArrayList<JSONObject>(data));
            }
        });
    }
    
    protected void deselectAll() {
        availableSelection.deselectAll();
        // get rid of leftover meta-host entries
        selectedHostData.clear();
        selectionRefresh();
    }
    
    protected void populateLabels(ListBox list) {
        String[] labelNames = AfeUtils.getLabelStrings();
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
        List<JSONObject> selectionArray = selectedHostData.getItems();
        for(JSONObject row : selectionArray ) {
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
