package autotest.afe;

import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.BooleanFilter;
import autotest.common.table.FieldFilter;
import autotest.common.table.ListFilter;
import autotest.common.table.SearchFilter;
import autotest.common.table.TableDecorator;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Widget;

class HostTableDecorator extends TableDecorator {
    SearchFilter hostnameFilter;
    LabelFilter labelFilter;
    ListFilter statusFilter;
    BooleanFilter lockedFilter;
    AclAccessibleFilter aclFilter;
    
    static class AclAccessibleFilter extends FieldFilter implements ClickListener {
        private CheckBox checkBox = new CheckBox("ACL accessible only");
        private JSONValue username;
        
        public AclAccessibleFilter() {
            super("acl_group__users__login");
            username = StaticDataRepository.getRepository().getData("user_login");
            checkBox.addClickListener(this);
        }
        
        public void onClick(Widget sender) {
            notifyListeners();
        }

        @Override
        public JSONValue getMatchValue() {
            return username;
        }

        @Override
        public Widget getWidget() {
            return checkBox;
        }

        @Override
        public boolean isActive() {
            return checkBox.isChecked();
        }
        
        public void setActive(boolean active) {
            checkBox.setChecked(active);
        }
    }
    
    public HostTableDecorator(HostTable table, int rowsPerPage) {
        super(table);
        table.sortOnColumn("Hostname");
        table.setRowsPerPage(rowsPerPage);
        addPaginators();
        
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray statuses = staticData.getData("host_statuses").isArray();
        String[] statusStrings = Utils.JSONtoStrings(statuses);
        
        hostnameFilter = new SearchFilter("hostname");
        hostnameFilter.setExactMatch(false);
        labelFilter = new LabelFilter();
        statusFilter = new ListFilter("status");
        statusFilter.setChoices(statusStrings);
        lockedFilter = new BooleanFilter("locked");
        aclFilter = new AclAccessibleFilter();
        
        addFilter("Hostname", hostnameFilter);
        addControl("Platform", labelFilter.getPlatformWidget());
        addFilter("Label", labelFilter);
        addFilter("Status", statusFilter);
        addFilter("Locked", lockedFilter);
        addFilter("ACL accessible only", aclFilter);
    }
}
