package autotest.afe;

import autotest.afe.create.CreateJobViewPresenter.JobCreateListener;
import autotest.common.SimpleCallback;
import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.table.SelectionManager;
import autotest.common.ui.ContextMenu;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.TabView;
import autotest.common.ui.TableActionsPanel.TableActionsListener;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.Command;

import java.util.Set;

public class HostListView extends TabView implements TableActionsListener {
    protected static final int HOSTS_PER_PAGE = 30;

    public interface HostListListener {
        public void onHostSelected(String hostname);
    }

    protected HostListListener hostListListener = null;
    private JobCreateListener jobCreateListener = null;

    public HostListView(HostListListener hostListListener, JobCreateListener jobCreateListener) {
        this.hostListListener = hostListListener;
        this.jobCreateListener = jobCreateListener;
    }

    @Override
    public String getElementId() {
        return "hosts";
    }

    protected SelectableProfileStaticHostTable table;
    protected HostTableDecorator hostTableDecorator;
    protected SelectionManager selectionManager;

    @Override
    public void initialize() {
        super.initialize();

        table = new SelectableProfileStaticHostTable(new HostDataSource());
        hostTableDecorator = new HostTableDecorator(table, HOSTS_PER_PAGE);

        selectionManager = hostTableDecorator.addSelectionManager(false);
        table.setWidgetFactory(selectionManager);
        hostTableDecorator.addTableActionsPanel(this, true);

        table.setClickable(true);
        table.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row, boolean isRightClick) {
                String hostname = row.get("hostname").isString().stringValue();
                hostListListener.onHostSelected(hostname);
            }

            public void onTableRefreshed() {}
        });

        addWidget(hostTableDecorator, "hosts_list");
    }

    @Override
    public void refresh() {
        super.refresh();
        table.refresh();
    }

    private void reverifySelectedHosts() {
        JSONObject params = new JSONObject();
        JSONArray hostIds = getSelectedHostIds();
        if (hostIds == null) {
            return;
        }

        params.put("id__in", hostIds);
        AfeUtils.callReverify(params, new SimpleCallback() {
            public void doCallback(Object source) {
               refresh();
            }
        }, "Hosts");
    }

    private void changeLockStatus(final boolean lock) {
        JSONArray hostIds = getSelectedHostIds();
        if (hostIds == null) {
            return;
        }

        AfeUtils.changeHostLocks(hostIds, lock, "Hosts", new SimpleCallback() {
            public void doCallback(Object source) {
                refresh();
            }
        });
    }

    private void reinstallSelectedHosts() {
        Set<JSONObject> selectedSet = getSelectedHosts();
        if (selectedSet == null) {
            return;
        }

        AfeUtils.scheduleReinstall(selectedSet, "Hosts", jobCreateListener);
    }

    private void handleHostsReservations(boolean reserve, boolean force) {
        JSONArray hostIds = getSelectedHostIds();
        if (hostIds == null) {
            return;
        }

        AfeUtils.handleHostsReservations(hostIds, reserve, force, "DONE", new SimpleCallback() {
            public void doCallback(Object source) {
                refresh();
            }
        });
    }

    private Set<JSONObject> getSelectedHosts() {
        Set<JSONObject> selectedSet = selectionManager.getSelectedObjects();
        if (selectedSet.isEmpty()) {
            NotifyManager.getInstance().showError("No hosts selected");
            return null;
        }
        return selectedSet;
    }

    private JSONArray getSelectedHostIds() {
        Set<JSONObject> selectedSet = getSelectedHosts();
        if (selectedSet == null) {
            return null;
        }

        JSONArray ids = new JSONArray();
        for (JSONObject jsonObj : selectedSet) {
            ids.set(ids.size(), jsonObj.get("id"));
        }

        return ids;
    }

    public ContextMenu getActionMenu() {
        ContextMenu menu = new ContextMenu();
        menu.addItem("Reverify hosts", new Command() {
            public void execute() {
                reverifySelectedHosts();
            }
        });
        menu.addItem("Lock hosts", new Command() {
            public void execute() {
                changeLockStatus(true);
            }
        });
        menu.addItem("Unlock hosts", new Command() {
            public void execute() {
                changeLockStatus(false);
            }
        });
        menu.addItem("Reinstall hosts", new Command() {
            public void execute() {
                reinstallSelectedHosts();
            }
        });
        menu.addItem("Reserve hosts", new Command() {
            public void execute() {
                handleHostsReservations(true, false);
            }
        });
        menu.addItem("Release hosts", new Command() {
            public void execute() {
                handleHostsReservations(false, false);
            }
        });
        menu.addItem("Force release hosts", new Command() {
            public void execute() {
                handleHostsReservations(false, true);
            }
        });

        return menu;
    }
}
