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
    OnlyIfNeededFilter excludeOnlyIfNeededFilter;
    
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
    
    static class OnlyIfNeededFilter extends CheckboxFilter {
        public OnlyIfNeededFilter() {
            super("exclude_only_if_needed_labels");
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
        excludeOnlyIfNeededFilter = new OnlyIfNeededFilter();
        
        addFilter("Hostname", hostnameFilter);
        addControl("Platform", labelFilter.getPlatformWidget());
        addFilter("Label", labelFilter);
        addFilter("Status", statusFilter);
        addFilter("Locked", lockedFilter);
        addFilter("ACL accessible only", aclFilter);
        addFilter("Exclude \"only if needed\" labels", excludeOnlyIfNeededFilter);
    }
}
