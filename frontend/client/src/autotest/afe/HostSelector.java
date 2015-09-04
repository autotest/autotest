package autotest.afe;

import autotest.common.Utils;
import autotest.common.table.ArrayDataSource;
import autotest.common.table.DataSource.DefaultDataCallback;
import autotest.common.table.DataSource.Query;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.table.SelectionManager;
import autotest.common.table.SelectionManager.SelectionListener;
import autotest.common.table.TableDecorator;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.SimplifiedList;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasValue;
import com.google.gwt.user.client.ui.Widget;
import com.google.gwt.user.client.Window;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * A widget to facilitate selection of a group of hosts for running a job.  The
 * widget displays two side-by-side tables; the left table is a normal
 * {@link HostTable} displaying available, unselected hosts, and the right table
 * displays selected hosts.  Click on a host in either table moves it to the
 * other (i.e. selects or deselects a host).  The widget provides several
 * convenience controls (such as one to remove all selected hosts) and a special
 * section for adding meta-host entries.
 */
public class HostSelector implements ClickHandler {
    private static final int TABLE_SIZE = 10;
    public static final String META_PREFIX = "Any ";
    public static int META_INDEX = 0;
    public static final String ONE_TIME = "(one-time host)";

    public static class HostSelection {
        public List<String> hosts = new ArrayList<String>();
        public List<String> profiles = new ArrayList<String>();
        public List<String> metaHosts = new ArrayList<String>();
        public List<String> metaHostProfiles = new ArrayList<String>();
        public List<String> oneTimeHosts = new ArrayList<String>();
    }

    public interface Display {
        public HasText getHostnameField();
        public HasValue<Boolean> getAllowOneTimeHostsField();
        public HasClickHandlers getAddByHostnameButton();
        public SimplifiedList getLabelList();
        public HasText getLabelNumberField();
        public HasClickHandlers getAddByLabelButton();
        public void setVisible(boolean visible);

        // a temporary measure until the table code gets refactored to support Passive View
        public void addTables(Widget availableTable, Widget selectedTable);
    }

    private ArrayDataSource<JSONObject> selectedHostData =
        new ArrayDataSource<JSONObject>(new String[] {"hostname"});

    private Display display;
    private HostDataSource hostDataSource = new HostDataSource();
    private ProfileDataSource profileDataSource = new ProfileDataSource();
    // availableTable needs its own data source
    private HostTable availableTable = new HostTable(new HostDataSource());
    private HostTableDecorator availableDecorator =
        new HostTableDecorator(availableTable, TABLE_SIZE);
    private ProfileSelectHostTable selectedTable = new ProfileSelectHostTable(selectedHostData);
    private TableDecorator selectedDecorator = new TableDecorator(selectedTable);
    private boolean enabled = true;

    private SelectionManager availableSelection;

    public void initialize() {
        selectedTable.setClickable(true);
        selectedTable.setRowsPerPage(TABLE_SIZE);
        selectedDecorator.addPaginators();

        Anchor clearSelection = new Anchor("Clear selection");
        clearSelection.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                deselectAll();
            }
        });
        selectedDecorator.setActionsWidget(clearSelection);

        availableTable.setClickable(true);
        availableDecorator.lockedFilter.setSelectedChoice("No");
        availableDecorator.aclFilter.setActive(true);
        availableDecorator.excludeAtomicGroupsFilter.setActive(true);
        availableSelection = availableDecorator.addSelectionManager(false);
        availableDecorator.addSelectionPanel(true);

        availableTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row, boolean isRightClick) {
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

            public void onClick(JSONValue id, String profile) {
                for (JSONObject row : selectedHostData.getItems()) {
                    if (row.get("id").equals(id)) {
                        selectedHostData.removeItem(row);
                        row.put("profile", new JSONString(profile));
                        selectedHostData.addItem(row);
                        break;
                    }
                }
            }
        });

        selectedTable.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row, boolean isRightClick) {
                if (isMetaEntry(row) || isOneTimeHost(row)) {
                    deselectRow(row);
                    selectionRefresh();
                } else {
                    availableSelection.deselectObject(row);
                }
            }

            public void onTableRefreshed() {}
        });
    }

    public void bindDisplay(Display display) {
        this.display = display;
        display.getAddByHostnameButton().addClickHandler(this);
        display.getAddByLabelButton().addClickHandler(this);
        display.addTables(availableDecorator, selectedDecorator);
        availableTable.setWidgetFactory(availableSelection);
        selectedTable.setWidgetFactory(availableSelection);

        populateLabels(display.getLabelList());
    }

    @Override
    public void onClick(ClickEvent event) {
        if (event.getSource() == display.getAddByLabelButton()) {
            onAddByLabel();
        } else if (event.getSource() == display.getAddByHostnameButton()) {
            onAddByHostname();
        }
    }

    private void onAddByHostname() {
        List<String> hosts = Utils.splitListWithSpaces(display.getHostnameField().getText());
        boolean allowOneTimeHosts = display.getAllowOneTimeHostsField().getValue();
        setSelectedHostnames(hosts, allowOneTimeHosts);
    }

    public void setSelectedHostnames(final List<String> hosts, final boolean allowOneTimeHosts) {
        // figure out which hosts exist in the system and which should be one-time hosts
        JSONObject params = new JSONObject();
        params.put("hostname__in", Utils.stringsToJSON(hosts));
        hostDataSource.query(params, new DefaultDataCallback () {
            @Override
            public void onQueryReady(Query query) {
                query.getPage(null, null, null, this);
            }

            @Override
            public void handlePage(List<JSONObject> data) {
                processAddByHostname(hosts, data, allowOneTimeHosts);
            }
        });
    }

    public void setSelectedHostnames(final List<String> hosts, final List<String> profiles, final boolean allowOneTimeHosts) {
        // figure out which hosts exist in the system and which should be one-time hosts
        JSONObject params = new JSONObject();
        params.put("hostname__in", Utils.stringsToJSON(hosts));
        hostDataSource.query(params, new DefaultDataCallback () {
            @Override
            public void onQueryReady(Query query) {
                query.getPage(null, null, null, this);
            }

            @Override
            public void handlePage(List<JSONObject> data) {
		/* when cloning, we have the original array of profiles that
		 * needs to be put back into the objects so the select box gets
		 * populated correctly */
                JSONObject o;
                int i;
                for (i = 0; i < data.size(); i++) {
                    o = data.get(i);
                    o.put("profile", new JSONString(profiles.get(i)));
                    data.set(i, o);
                }
                processAddByHostname(hosts, data, allowOneTimeHosts);
            }
        });
    }

    private List<String> findOneTimeHosts(List<String> requestedHostnames,
                                          List<JSONObject> foundHosts) {
        Set<String> existingHosts = new HashSet<String>();
        for (JSONObject host : foundHosts) {
            existingHosts.add(Utils.jsonToString(host.get("hostname")));
        }

        List<String> oneTimeHostnames = new ArrayList<String>();
        for (String hostname : requestedHostnames) {
            if (!existingHosts.contains(hostname)) {
                oneTimeHostnames.add(hostname);
            }
        }

        return oneTimeHostnames;
    }

    private void processAddByHostname(final List<String> requestedHostnames,
                                      List<JSONObject> foundHosts,
                                      boolean allowOneTimeHosts) {
        List<String> oneTimeHostnames = findOneTimeHosts(requestedHostnames, foundHosts);
        if (!allowOneTimeHosts && !oneTimeHostnames.isEmpty()) {
            NotifyManager.getInstance().showError("Hosts not found: " +
                                                  Utils.joinStrings(", ", oneTimeHostnames));
            return;
        }

        // deselect existing non-metahost hosts
        // iterate over copy to allow modification
        for (JSONObject host : new ArrayList<JSONObject>(selectedHostData.getItems())) {
            if (isOneTimeHost(host)) {
                selectedHostData.removeItem(host);
            }
        }
        availableSelection.deselectAll();

        // add one-time hosts
        for (String hostname : oneTimeHostnames) {
            JSONObject oneTimeObject = new JSONObject();
            JSONArray profiles = new JSONArray();
            profiles.set(0, new JSONString("N/A"));
            oneTimeObject.put("hostname", new JSONString(hostname));
            oneTimeObject.put("platform", new JSONString(ONE_TIME));
            oneTimeObject.put("profiles", profiles);
            oneTimeObject.put("other_labels", new JSONString(""));
            oneTimeObject.put("status", new JSONString(""));
            oneTimeObject.put("locked_text", new JSONString(""));
            oneTimeObject.put("id", new JSONNumber(--META_INDEX));
            selectRow(oneTimeObject);
        }

        // add existing hosts
        availableSelection.selectObjects(foundHosts); // this refreshes the selection
    }

    private void onAddByLabel() {
        SimplifiedList labelList = display.getLabelList();
        String labelName = labelList.getSelectedName();
        String label = AfeUtils.decodeLabelName(labelName);
        String number = display.getLabelNumberField().getText();
        try {
            Integer.parseInt(number);
        }
        catch (NumberFormatException exc) {
            String error = "Invalid number " + number;
            NotifyManager.getInstance().showError(error);
            return;
        }

        addMetaHosts(label, number, "");
    }

    public void addMetaHosts(final String label, final String number, final String profile) {
        JSONObject params = new JSONObject();
        profileDataSource.query(params, new DefaultDataCallback () {
            @Override
            public void onQueryReady(Query query) {
                query.getPage(null, null, null, this);
            }

            @Override
            public void handlePage(List<JSONObject> data) {
                processAddByLabel(label, number, profile, data);
            }
        });
    }

    private void processAddByLabel(final String label, final String number, final String profile, List<JSONObject> data) {
        JSONObject metaObject = new JSONObject();
        JSONArray profiles = new JSONArray();
        int i = 0;
        metaObject.put("hostname", new JSONString(META_PREFIX + number));
        metaObject.put("platform", new JSONString(label));
        metaObject.put("other_labels", new JSONString(""));
        metaObject.put("status", new JSONString(""));
        metaObject.put("locked_text", new JSONString(""));
        metaObject.put("id", new JSONNumber(--META_INDEX));
        metaObject.put("profile", new JSONString(profile));
        for (JSONObject prof : data) {
             String p = prof.get("name").toString();
             // JSON seems to insert extra quotes
             profiles.set(i, new JSONString(p.substring(1, p.length()-1)));
             i++;
        }
        metaObject.put("profiles", profiles);
        selectRow(metaObject);
        selectionRefresh();
    }

    private void selectRow(JSONObject row) {
        selectedHostData.addItem(row);
    }

    private void deselectRow(JSONObject row) {
        selectedHostData.removeItem(row);
    }

    private void deselectAll() {
        availableSelection.deselectAll();
        // get rid of leftover meta-host entries
        selectedHostData.clear();
        selectionRefresh();
    }

    private void populateLabels(SimplifiedList list) {
        String[] labelNames = AfeUtils.getLabelStrings();
        for (String labelName : labelNames) {
            list.addItem(labelName, "");
        }
    }

    private String getProfile(JSONObject row) {
        return row.get("profile").isString().stringValue();
    }

    private String getHostname(JSONObject row) {
        return row.get("hostname").isString().stringValue();
    }

    private boolean isMetaEntry(JSONObject row) {
        return getHostname(row).startsWith(META_PREFIX);
    }

    private int getMetaNumber(JSONObject row) {
        return Integer.parseInt(getHostname(row).substring(META_PREFIX.length()));
    }

    private boolean isOneTimeHost(JSONObject row) {
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
        if (!enabled) {
            return selection;
        }

        for (JSONObject row : selectedHostData.getItems() ) {
            if (isMetaEntry(row)) {
                int count =  getMetaNumber(row);
                String platform = row.get("platform").isString().stringValue();
                String profile = getProfile(row);
                for(int counter = 0; counter < count; counter++) {
                    selection.metaHosts.add(platform);
                    selection.metaHostProfiles.add(profile);
                }
            }
            else {
                String hostname = getHostname(row);
                if (isOneTimeHost(row)) {
                    /*
                     * Need to avoid trying to install one-time hosts.
                     */
                    hostname += "#N/A";
                    selection.oneTimeHosts.add(hostname);
                } else {
                    selection.hosts.add(hostname);
                    selection.profiles.add(getProfile(row));
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
        setEnabled(true);
    }

    /**
     * Refresh as necessary for selection change, but don't make any RPCs.
     */
    private void selectionRefresh() {
        selectedTable.refresh();
        updateHostnameList();
    }

    private void updateHostnameList() {
        List<String> hostnames = new ArrayList<String>();
        for (JSONObject hostObject : selectedHostData.getItems()) {
            if (!isMetaEntry(hostObject)) {
                hostnames.add(Utils.jsonToString(hostObject.get("hostname")));
            }
        }

        String hostList = Utils.joinStrings(", ", hostnames);
        display.getHostnameField().setText(hostList);
    }

    public void refresh() {
        availableTable.refresh();
        selectionRefresh();
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
        display.setVisible(enabled);
    }
}
