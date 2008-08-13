package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.FocusListener;
import com.google.gwt.user.client.ui.HasVerticalAlignment;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.MultiWordSuggestOracle;
import com.google.gwt.user.client.ui.SuggestBox;
import com.google.gwt.user.client.ui.SuggestionEvent;
import com.google.gwt.user.client.ui.SuggestionHandler;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.HashMap;
import java.util.HashSet;

public class ExistingGraphsFrontend extends Composite {
    
    private JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    private CheckBox normalize = new CheckBox("Normalize Performance (allows multiple benchmarks" +
                                              " on one graph)");
    private MultiWordSuggestOracle oracle = new MultiWordSuggestOracle();
    private TextBox hostname = new TextBox();
    private SuggestBox hostnameSuggest = new SuggestBox(oracle, hostname);
    private ListBox benchmark = new ListBox();
    private TextBox kernel = new TextBox();
    private JSONObject hostsAndTests = null;
    private Button graphButton = new Button("Graph");
    FlexTable table = new FlexTable();
    
    public ExistingGraphsFrontend() {
        normalize.addClickListener(new ClickListener() {
            public void onClick(Widget w) {
                benchmark.setMultipleSelect(normalize.isChecked());
                int selectedIndex = benchmark.getSelectedIndex();
                for (int i = 0; i < benchmark.getItemCount(); i++) {
                    benchmark.setItemSelected(i, i == selectedIndex);
                }
            }
        });
        
        hostnameSuggest.addFocusListener(new FocusListener() {
            public void onLostFocus(Widget w) {
                refreshTests();
            }
            
            public void onFocus(Widget w) {
                // Don't do anything
            }
        });
        hostnameSuggest.addEventHandler(new SuggestionHandler() {
            public void onSuggestionSelected(SuggestionEvent s) {
                refreshTests();
            }
        });

        benchmark.addItem("(Please select a hostname first)");
        
        graphButton.addClickListener(new ClickListener() {
            public void onClick(Widget w) {
                showGraph();
            }
        });

        kernel.setText("all");
        
        table.setWidget(0, 0, normalize);
        table.getFlexCellFormatter().setColSpan(0, 0, 2);
        addControl("Hostname:", hostnameSuggest);
        addControl("Benchmark:", benchmark);
        addControl("Kernel:", kernel);
        table.setWidget(table.getRowCount(), 1, graphButton);

        table.getColumnFormatter().setWidth(0, "1px");
        
        initWidget(table);
    }
    
    public void refresh() {
        setEnabled(false);
        rpcProxy.rpcCall("get_hosts_and_tests", new JSONObject(), new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                hostsAndTests = result.isObject();
                oracle.clear();
                for (String host : hostsAndTests.keySet()) {
                    oracle.add(host);
                }
                setEnabled(true);
            }
        });
    }
    
    private void addControl(String text, Widget widget) {
        int row = table.getRowCount();
        table.setText(row, 0, text);
        table.setWidget(row, 1, widget);
        table.getFlexCellFormatter().setStylePrimaryName(row, 0, "field-name");
        table.getFlexCellFormatter().setVerticalAlignment(row, 0, HasVerticalAlignment.ALIGN_TOP);
    }
    
    private void setEnabled(boolean enabled) {
        normalize.setEnabled(enabled);
        hostname.setEnabled(enabled);
        benchmark.setEnabled(enabled);
        kernel.setEnabled(enabled);
        graphButton.setEnabled(enabled);
    }
    
    private void refreshTests() {
        JSONValue value = hostsAndTests.get(hostnameSuggest.getText());
        if (value == null) {
            return;
        }
        
        HashSet<String> selectedTests = new HashSet<String>();
        for (int i = 0; i < benchmark.getItemCount(); i++) {
            if (benchmark.isItemSelected(i)) {
                selectedTests.add(benchmark.getValue(i));
            }
        }
        
        JSONArray tests = value.isObject().get("tests").isArray();
        benchmark.clear();
        for (int i = 0; i < tests.size(); i++) {
            String test = tests.get(i).isString().stringValue();
            benchmark.addItem(test);
            if (selectedTests.contains(test)) {
                benchmark.setItemSelected(i, true);
            }
        }
    }
    
    private void showGraph() {
        String hostnameStr = hostnameSuggest.getText();
        
        JSONValue value = hostsAndTests.get(hostnameStr);
        if (value == null) {
            return;
        }
        
        String url;
        HashMap<String, String> args = new HashMap<String, String>();
        args.put("kernel", kernel.getText());
        
        if (normalize.isChecked()) {
            url = "/tko/machine_aggr.cgi?";
            final JSONArray tests = new JSONArray();
            for (int i = 0; i < benchmark.getItemCount(); i++) {
                if (benchmark.isItemSelected(i)) {
                    tests.set(tests.size(), new JSONString(benchmark.getValue(i)));
                }
            }
            
            args.put("machine", hostnameStr);

            StringBuilder arg = new StringBuilder();
            for (int i = 0; i < tests.size(); i++) {
                String test = tests.get(i).isString().stringValue();
                String key = getKey(test);
                if (i != 0) {
                    arg.append(",");
                }
                arg.append(test);
                arg.append(":");
                arg.append(key);
            }
            args.put("benchmark_key", arg.toString());
        } else {
            int benchmarkIndex = benchmark.getSelectedIndex();
            if (benchmarkIndex == -1) {
                return;
            }
            
            url = "/tko/machine_test_attribute_graph.cgi?";
            
            JSONObject hostObject = value.isObject();
            int machine = (int) hostObject.get("id").isNumber().doubleValue();
            String benchmarkStr = benchmark.getValue(benchmarkIndex);
            
            args.put("machine", String.valueOf(machine));
            args.put("benchmark", benchmarkStr);
            args.put("key", getKey(benchmarkStr));
        }
        Window.open(url + Utils.encodeUrlArguments(args), "_blank", "");
    }
    
    private String getKey(String benchmark) {
        JSONObject benchmarkKey =
            StaticDataRepository.getRepository().getData("benchmark_key").isObject();
        return benchmarkKey.get(benchmark.replaceAll("\\..*", "")).isString().stringValue();
    }
}
