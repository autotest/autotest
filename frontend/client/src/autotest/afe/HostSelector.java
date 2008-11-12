package autotest.afe;

import autotest.common.Utils;
import autotest.common.table.ArrayDataSource;
import autotest.common.table.SelectionManager;
import autotest.common.table.TableDecorator;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.table.SelectionManager.SelectionListener;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.SimpleHyperlink;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

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
    public static final String ONE_TIME = "(one-time host)";
    
    static class HostSelection {
        public List<String> hosts = new ArrayList<String>();
        public List<String> metaHosts = new ArrayList<String>();
        public List<String> oneTimeHosts = new ArrayList<String>();
    }
    
    protected ArrayDataSource<JSONObject> selectedHostData =
        new ArrayDataSource<JSONObject>(new String[] {"hostname", "platform"});
    
    protected HostTable availableTable = new HostTable(new HostDataSource());
    protected HostTableDecorator availableDecorator = 
        new HostTableDecorator(availableTable, TABLE_SIZE);
    protected HostTable selectedTable = new HostTable(selectedHostData);
    protected TableDecorator selectedDecorator = 
        new TableDecorator(selectedTable);
    
    protected SelectionManager availableSelection;
    
    public HostSelector() {
        selectedTable.setClickable(true);
        selectedTable.setRowsPerPage(TABLE_SIZE);
        selectedDecorator.addPaginators();

        SimpleHyperlink clearSelection = new SimpleHyperlink("Clear selection");
        clearSelection.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                deselectAll();
            } 
        });
        selectedDecorator.setActionsWidget(clearSelection);

        availableTable.setClickable(true);
        availableDecorator.lockedFilter.setSelectedChoice("No");
        availableDecorator.aclFilter.setActive(true);
        availableDecorator.excludeOnlyIfNeededFilter.setActive(true);
        availableSelection = availableDecorator.addSelectionManager(false);
        availableDecorator.addSelectionPanel(true);
        
        availableTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                availableSelection.toggleSelected(row);
            } 
            
            public void onTableRefreshed() {}
        });
        
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
                if (isMetaEntry(row) || isOneTimeHost(row)) {
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
                
                selectMetaHost(label, number);
                selectionRefresh();
            }
        });
        RootPanel.get("create_meta_select").add(metaLabelSelect);
        RootPanel.get("create_meta_number").add(metaNumber);
        RootPanel.get("create_meta_button").add(metaButton);
        
        final TextBox oneTimeHostField = new TextBox();
        final Button oneTimeHostButton = new Button("Add");
        oneTimeHostButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                List<String> hosts = Utils.splitListWithSpaces(oneTimeHostField.getText());
                for (String hostname : hosts) {
                    JSONObject oneTimeObject = new JSONObject();
                    oneTimeObject.put("hostname", new JSONString(hostname));
                    oneTimeObject.put("platform", new JSONString(ONE_TIME));
                    selectRow(oneTimeObject);
                }
                selectionRefresh();
            }
        });
        RootPanel.get("create_one_time_field").add(oneTimeHostField);
        RootPanel.get("create_one_time_button").add(oneTimeHostButton);
    }
    
    protected void selectMetaHost(String label, String number) {
        JSONObject metaObject = new JSONObject();
        metaObject.put("hostname", new JSONString(META_PREFIX + number));
        metaObject.put("platform", new JSONString(label));
        metaObject.put("labels", new JSONArray());
        metaObject.put("status", new JSONString(""));
        metaObject.put("locked", new JSONNumber(0));
        selectRow(metaObject);
    }
    
    protected void selectRow(JSONObject row) {
        selectedHostData.addItem(row);
    }
    
    protected void deselectRow(JSONObject row) {
        selectedHostData.removeItem(row);
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
    
    protected boolean isOneTimeHost(JSONObject row) {
        JSONString platform = row.get("platform").isString();
        if (platform == null) {
            return false;
        }
        return platform.stringValue().equals(ONE_TIME);
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
                if (isOneTimeHost(row)) {
                    selection.oneTimeHosts.add(hostname);
                } else {
                    selection.hosts.add(hostname);
                }
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
    }
    
    public void refresh() {
        availableTable.refresh();
        selectionRefresh();
    }
}
