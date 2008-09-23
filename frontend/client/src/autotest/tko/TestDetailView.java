package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.Utils;
import autotest.common.ui.DetailView;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RealHyperlink;

import com.google.gwt.http.client.Request;
import com.google.gwt.http.client.RequestBuilder;
import com.google.gwt.http.client.RequestCallback;
import com.google.gwt.http.client.RequestException;
import com.google.gwt.http.client.Response;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.DisclosureEvent;
import com.google.gwt.user.client.ui.DisclosureHandler;
import com.google.gwt.user.client.ui.DisclosurePanel;
import com.google.gwt.user.client.ui.FlowPanel;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RootPanel;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

class TestDetailView extends DetailView {
    private static final int NO_TEST_ID = -1;
    
    private int testId = NO_TEST_ID;
    private String jobTag;
    private List<LogFileViewer> logFileViewers = new ArrayList<LogFileViewer>();
    private RealHyperlink logLink = new RealHyperlink("(view all logs)");

    private Panel logPanel;
    
    private class LogFileViewer extends Composite implements DisclosureHandler, RequestCallback {
        private static final String FAILED_TEXT = "Failed to retrieve log";
        private DisclosurePanel panel;
        private String logFilePath;
        
        public LogFileViewer(String logFilePath, String logFileName) {
            this.logFilePath = logFilePath;
            panel = new DisclosurePanel(logFileName);
            panel.addEventHandler(this);
            panel.addStyleName("log-file-panel");
            initWidget(panel);
        }
        
        public void onOpen(DisclosureEvent event) {
            RequestBuilder builder = new RequestBuilder(RequestBuilder.GET, getLogUrl());
            try {
                builder.sendRequest("", this);
                setStatusText("Loading...");
            } catch (RequestException exc) {
                onRequestFailure();
            }
        }

        private String getLogUrl() {
            return Utils.getLogsURL(jobTag + "/" + logFilePath);
        }

        private void setLogText(String text) {
            panel.clear();
            Label label = new Label(text);
            label.setStyleName("log-file-text");
            panel.add(label);
        }
        
        private void setStatusText(String status) {
            panel.clear();
            panel.add(new HTML("<i>" + status + "</i>"));
        }

        public void onClose(DisclosureEvent event) {}

        public void onError(Request request, Throwable exception) {
            onRequestFailure();
        }

        private void onRequestFailure() {
            setStatusText(FAILED_TEXT);
        }

        public void onResponseReceived(Request request, Response response) {
            if (response.getStatusCode() != 200) {
                onRequestFailure();
                return;
            }
            
            String logText = response.getText();
            if (logText.equals("")) {
                setStatusText("Log file is empty");
            } else {
                setLogText(logText);
            }
        }
    }
    
    @Override
    public void initialize() {
        super.initialize();
        
        logPanel = new FlowPanel();
        RootPanel.get("td_log_files").add(logPanel);
        
        logLink.setOpensNewWindow(true);
        RootPanel.get("td_view_logs_link").add(logLink);
    }

    private void addLogViewers(String testName) {
        logPanel.clear();
        addLogFileViewer(testName + "/debug/stdout", "Test stdout");
        addLogFileViewer(testName + "/debug/stderr", "Test stderr");
        addLogFileViewer("status.log", "Job status log");
        addLogFileViewer("debug/autoserv.stdout", "Job autoserv stdout");
        addLogFileViewer("debug/autoserv.stderr", "Job autoserv stderr");
    }

    private void addLogFileViewer(String logPath, String logName) {
        LogFileViewer viewer = new LogFileViewer(logPath, logName);
        logFileViewers.add(viewer);
        logPanel.add(viewer);
    }

    @Override
    protected void fetchData() {
        JSONObject params = new JSONObject();
        params.put("test_idx", new JSONNumber(testId));
        rpcProxy.rpcCall("get_detailed_test_views", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                JSONObject test;
                try {
                    test = Utils.getSingleValueFromArray(result.isArray()).isObject();
                }
                catch (IllegalArgumentException exc) {
                    NotifyManager.getInstance().showError("No such job found");
                    resetPage();
                    return;
                }
                
                showTest(test);
            }
            
            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                resetPage();
            }
        });
    }
    
    @Override
    protected void setObjectId(String id) {
        try {
            testId = Integer.parseInt(id);
        }
        catch (NumberFormatException exc) {
            throw new IllegalArgumentException();
        }
    }
    
    @Override
    protected String getObjectId() {
        if (testId == NO_TEST_ID) {
            return NO_OBJECT;
        }
        return Integer.toString(testId);
    }

    @Override
    protected String getDataElementId() {
        return "td_data";
    }

    @Override
    protected String getFetchControlsElementId() {
        return "td_fetch_controls";
    }

    @Override
    protected String getNoObjectText() {
        return "No test selected";
    }

    @Override
    protected String getTitleElementId() {
        return "td_title";
    }

    @Override
    public String getElementId() {
        return "test_detail_view";
    }
    
    @Override
    public void display() {
        super.display();
        CommonPanel.getPanel().setConditionVisible(false);
    }

    protected void showTest(JSONObject test) {
        String testName = test.get("test_name").isString().stringValue();
        jobTag = test.get("job_tag").isString().stringValue();
        
        showText(testName, "td_test");
        showText(jobTag, "td_job_tag");
        showField(test, "job_name", "td_job_name");
        showField(test, "status", "td_status");
        showField(test, "reason", "td_reason");
        showField(test, "test_started_time", "td_test_started");
        showField(test, "test_finished_time", "td_test_finished");
        showField(test, "hostname", "td_hostname");
        showField(test, "platform", "td_platform");
        showField(test, "kernel", "td_kernel");
        
        String[] labels = Utils.JSONtoStrings(test.get("labels").isArray());
        String labelList = Utils.joinStrings(", ", Arrays.asList(labels));
        if (labelList.equals("")) {
            labelList = "none";
        }
        showText(labelList, "td_test_labels");
        
        logLink.setHref(Utils.getLogsURL(jobTag));
        addLogViewers(testName);
        
        displayObjectData("Test " + testName + " (job " + jobTag + ")");
    }
}
