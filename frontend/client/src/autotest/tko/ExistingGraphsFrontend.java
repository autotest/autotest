package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.ui.TabView;

import com.google.gwt.event.dom.client.BlurEvent;
import com.google.gwt.event.dom.client.BlurHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.logical.shared.SelectionEvent;
import com.google.gwt.event.logical.shared.SelectionHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.MultiWordSuggestOracle;
import com.google.gwt.user.client.ui.SuggestBox;
import com.google.gwt.user.client.ui.SuggestOracle;
import com.google.gwt.user.client.ui.TextBox;

import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

public class ExistingGraphsFrontend extends GraphingFrontend {

    private CheckBox normalize = new CheckBox("Normalize Performance (allows multiple benchmarks" +
                                              " on one graph)");
    private MultiWordSuggestOracle oracle = new MultiWordSuggestOracle();
    private TextBox hostname = new TextBox();
    private SuggestBox hostnameSuggest = new SuggestBox(oracle, hostname);
    private ListBox benchmark = new ListBox();
    private TextBox kernel = new TextBox();
    private JSONObject hostsAndTests = null;
    private Button graphButton = new Button("Graph");

    public ExistingGraphsFrontend(final TabView parent) {
        normalize.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                normalizeClicked();
            }
        });
        
        hostnameSuggest.getTextBox().addBlurHandler(new BlurHandler() {
            public void onBlur(BlurEvent event) {
                refreshTests();
            }
        });
        hostnameSuggest.addSelectionHandler(new SelectionHandler<SuggestOracle.Suggestion>() {
            public void onSelection(SelectionEvent<SuggestOracle.Suggestion> event) {
                refreshTests();
            }
        });

        benchmark.addItem("(Please select a hostname first)");
        
        graphButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                parent.updateHistory();
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

    private void getHostsAndTests(final SimpleCallback onFinished) {
        setEnabled(false);
        rpcProxy.rpcCall("get_hosts_and_tests", new JSONObject(), new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                hostsAndTests = result.isObject();
                onFinished.doCallback(null);
                setEnabled(true);
            }
        });
    }

    @Override
    public void refresh() {
        getHostsAndTests(new SimpleCallback() {
            public void doCallback(Object source) {
                oracle.clear();
                for (String host : hostsAndTests.keySet()) {
                    oracle.add(host);
                }
            } 
        });
    }

    @Override
    public void addToHistory(Map<String, String> args) {
        args.put("normalize", String.valueOf(normalize.getValue()));
        args.put("hostname", hostname.getText());

        // Add the selected benchmarks
        StringBuilder benchmarks = new StringBuilder();
        for (int i = 0; i < benchmark.getItemCount(); i++) {
            if (benchmark.isItemSelected(i)) {
                benchmarks.append(benchmark.getValue(i));
                benchmarks.append(",");
            }
        }

        args.put("benchmark", benchmarks.toString());
        args.put("kernel", kernel.getText());
    }

    @Override
    public void handleHistoryArguments(final Map<String, String> args) {
        hostname.setText(args.get("hostname"));
        normalize.setValue(Boolean.parseBoolean(args.get("normalize")));
        normalizeClicked();
        kernel.setText(args.get("kernel"));

        getHostsAndTests(new SimpleCallback() {
            public void doCallback(Object source) {
                refreshTests();

                Set<String> benchmarks =
                    new HashSet<String>(Arrays.asList(args.get("benchmark").split(",")));
                for (int i = 0; i < benchmark.getItemCount(); i++) {
                    benchmark.setItemSelected(i, benchmarks.contains(benchmark.getValue(i)));
                }
            } 
        });
    }

    @Override
    protected void addAdditionalEmbeddingParams(JSONObject params) {
        // No embedding
    }

    // Change the state of the page based on the status of the "normalize" checkbox
    private void normalizeClicked() {
        benchmark.setMultipleSelect(normalize.getValue());
        // when switching to single-select, we need to manually force the selection to a single item
        int selectedIndex = benchmark.getSelectedIndex();
        for (int i = 0; i < benchmark.getItemCount(); i++) {
            benchmark.setItemSelected(i, i == selectedIndex);
        }
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
            String test = Utils.jsonToString(tests.get(i));
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
        
        if (normalize.getValue()) {
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
                String test = Utils.jsonToString(tests.get(i));
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
            String machine = Utils.jsonToString(hostObject.get("id"));
            String benchmarkStr = benchmark.getValue(benchmarkIndex);
            
            args.put("machine", machine);
            args.put("benchmark", benchmarkStr);
            args.put("key", getKey(benchmarkStr));
        }
        Utils.openUrlInNewWindow(url + Utils.encodeUrlArguments(args));
    }
    
    private String getKey(String benchmark) {
        JSONObject benchmarkKey =
            StaticDataRepository.getRepository().getData("benchmark_key").isObject();
        return Utils.jsonToString(benchmarkKey.get(benchmark.replaceAll("\\..*", "")));
    }

    @Override
    public String getFrontendId() {
        return "existing_graphs";
    }
}
