package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.SimpleDialog;
import autotest.tko.TableView.TableViewConfig;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.HTML;

class MachineQualHistogram extends Plot {
    public MachineQualHistogram() {
        super("create_qual_histogram");
    }

    /**
     * drilldownParams contains:
     * * type: "normal", "not_applicable", or "empty"
     * for type "normal":
     *   * filterString: SQL filter for selected bucket
     * for type "not_applicable":
     *   * hosts: HTML list of hosts in this bucket
     */
    @Override
    protected void showDrilldownImpl(JSONObject drilldownParams) {
        String type = Utils.jsonToString(drilldownParams.get("type"));
        if (type.equals("normal")) {
            String filterString = Utils.jsonToString(drilldownParams.get("filterString"));
            showNormalDrilldown(filterString);
        } else if (type.equals("not_applicable")) {
            String hosts = Utils.jsonToString(drilldownParams.get("hosts"));
            showNADialog(hosts);
        } else if (type.equals("empty")) {
            showEmptyDialog();
        }
    }

    private void showNormalDrilldown(final String filterString) {
        CommonPanel.getPanel().setSqlCondition(filterString);
        listener.onSwitchToTable(TableViewConfig.PASS_RATE);
    }

    private void showNADialog(String hosts) {
        new SimpleDialog("Did not run any of the selected tests:", new HTML(hosts)).center();
    }

    private void showEmptyDialog() {
        new SimpleDialog("No hosts in this pass rate range", new HTML()).center();
    }
}
