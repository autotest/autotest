package autotest.afe;

import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.BooleanFilter;
import autotest.common.table.CheckboxFilter;
import autotest.common.table.ListFilter;
import autotest.common.table.SearchFilter;
import autotest.common.table.TableDecorator;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.ArrayList;
import java.util.List;

class HostTableDecorator extends TableDecorator implements SimpleCallback {
    SearchFilter hostnameFilter;
    LabelFilter labelFilter;
    ListFilter statusFilter;
    BooleanFilter lockedFilter;
    ListFilter lockedByFilter;
    AclAccessibleFilter aclFilter;
    AtomicGroupFilter excludeAtomicGroupsFilter;

    static class AclAccessibleFilter extends CheckboxFilter {
        private JSONValue username;

        public AclAccessibleFilter() {
            super("aclgroup__users__login");
            username = new JSONString(StaticDataRepository.getRepository().getCurrentUserLogin());
        }

        @Override
        public JSONValue getMatchValue() {
            return username;
        }
    }

    static class AtomicGroupFilter extends CheckboxFilter {
        public AtomicGroupFilter() {
            super("exclude_atomic_group_hosts");
        }

        @Override
        public JSONValue getMatchValue() {
            return JSONBoolean.getInstance(true);
        }
    }

    public HostTableDecorator(HostTable table, int rowsPerPage) {
        super(table);
        table.sortOnColumn("hostname");  /* Case sensitive name */
        table.setRowsPerPage(rowsPerPage);
        addPaginators();

        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray statuses = staticData.getData("host_statuses").isArray();
        String[] statusStrings = Utils.JSONtoStrings(statuses);

        JSONArray users = staticData.getData("users").isArray();
        List<String> userStrings = new ArrayList<String>();
        for (int i = 0; i < users.size(); i++) {
            JSONObject user = users.get(i).isObject();
            userStrings.add(Utils.jsonToString(user.get("login")));
        }

        hostnameFilter = new SearchFilter("hostname", true);
        labelFilter = new LabelFilter();
        statusFilter = new ListFilter("status");
        statusFilter.setChoices(statusStrings);
        lockedFilter = new BooleanFilter("locked");
        lockedByFilter = new ListFilter("locked_by__login");
        lockedByFilter.setChoices(userStrings.toArray(new String[userStrings.size()]));
        aclFilter = new AclAccessibleFilter();
        excludeAtomicGroupsFilter = new AtomicGroupFilter();

        updateLockedByEnabled();
        lockedFilter.addCallback(this);

        addFilter("Hostname", hostnameFilter);
        addControl("Platform", labelFilter.getPlatformWidget());
        addFilter("Label", labelFilter);
        addFilter("Status", statusFilter);
        addFilter("Locked", lockedFilter);
        addFilter("Locked By", lockedByFilter);
        addFilter("ACL accessible only", aclFilter);
        addFilter("Exclude atomic groups", excludeAtomicGroupsFilter);
    }

    @Override
    public void doCallback(Object source) {
        assert source == lockedFilter;
        updateLockedByEnabled();
    }

    private void updateLockedByEnabled() {
        if (lockedFilter.isActive() && lockedFilter.isSelected()) {
            lockedByFilter.setEnabled(true);
        } else {
            lockedByFilter.setEnabled(false);
        }
    }
}
