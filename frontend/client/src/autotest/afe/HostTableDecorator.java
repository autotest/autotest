package autotest.afe;

import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.BooleanFilter;
import autotest.common.table.CheckboxFilter;
import autotest.common.table.ListFilter;
import autotest.common.table.SearchFilter;
import autotest.common.table.TableDecorator;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

class HostTableDecorator extends TableDecorator {
    SearchFilter hostnameFilter;
    LabelFilter labelFilter;
    ListFilter statusFilter;
    BooleanFilter lockedFilter;
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
        
        hostnameFilter = new SearchFilter("hostname", true);
        labelFilter = new LabelFilter();
        statusFilter = new ListFilter("status");
        statusFilter.setChoices(statusStrings);
        lockedFilter = new BooleanFilter("locked");
        aclFilter = new AclAccessibleFilter();
        excludeAtomicGroupsFilter = new AtomicGroupFilter();
        
        addFilter("Hostname", hostnameFilter);
        addControl("Platform", labelFilter.getPlatformWidget());
        addFilter("Label", labelFilter);
        addFilter("Status", statusFilter);
        addFilter("Locked", lockedFilter);
        addFilter("ACL accessible only", aclFilter);
        addFilter("Exclude atomic groups", excludeAtomicGroupsFilter);
    }
}
