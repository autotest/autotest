package autotest.afe.create;

import autotest.afe.AfeUtils;
import autotest.afe.CheckBoxPanel;
import autotest.afe.ControlTypeSelect;
import autotest.afe.HostSelector;
import autotest.afe.IButton;
import autotest.afe.ICheckBox;
import autotest.afe.ITextArea;
import autotest.afe.ITextBox;
import autotest.afe.TestSelector;
import autotest.afe.TestSelector.TestSelectorListener;
import autotest.common.JSONArrayList;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.RadioChooser;
import autotest.common.ui.SimplifiedList;

import com.google.gwt.event.dom.client.BlurEvent;
import com.google.gwt.event.dom.client.BlurHandler;
import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.dom.client.KeyCodes;
import com.google.gwt.event.dom.client.KeyPressEvent;
import com.google.gwt.event.dom.client.KeyPressHandler;
import com.google.gwt.event.logical.shared.CloseEvent;
import com.google.gwt.event.logical.shared.CloseHandler;
import com.google.gwt.event.logical.shared.HasCloseHandlers;
import com.google.gwt.event.logical.shared.HasOpenHandlers;
import com.google.gwt.event.logical.shared.OpenEvent;
import com.google.gwt.event.logical.shared.OpenHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONNull;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.DisclosurePanel;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasValue;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class CreateJobViewPresenter implements TestSelectorListener {
    public static interface Display {
        public CheckBoxPanel.Display getCheckBoxPanelDisplay();
        public ControlTypeSelect.Display getControlTypeSelectDisplay();
        public TestSelector.Display getTestSelectorDisplay();
        public IButton getEditControlButton();
        public HasText getJobName();
        public SimplifiedList getPriorityList();
        public HasText getTimeout();
        public HasText getMaxRuntime();
        public HasText getEmailList();
        public ICheckBox getSkipVerify();
        public RadioChooser.Display getRebootBefore();
        public RadioChooser.Display getRebootAfter();
        public HasValue<Boolean> getParseFailedRepair();
        public ICheckBox getHostless();
        public HasValue<Boolean> getReserveHosts();
        public HostSelector.Display getHostSelectorDisplay();
        public SimplifiedList getDroneSet();
        public ITextBox getSynchCountInput();
        public ITextArea getControlFile();
        public void setControlFilePanelOpen(boolean isOpen);
        public ICheckBox getRunNonProfiledIteration();
        public ITextBox getKernel();
        public ITextBox getKernelCmdline();
        public HasText getViewLink();
        public HasCloseHandlers<DisclosurePanel> getControlFilePanelClose();
        public HasOpenHandlers<DisclosurePanel> getControlFilePanelOpen();
        public IButton getSubmitJobButton();
        public HasClickHandlers getCreateTemplateJobButton();
        public HasClickHandlers getResetButton();
    }

    private static final String EDIT_CONTROL_STRING = "Edit control file";
    private static final String UNEDIT_CONTROL_STRING= "Revert changes";
    private static final String VIEW_CONTROL_STRING = "View control file";
    private static final String HIDE_CONTROL_STRING = "Hide control file";

    public interface JobCreateListener {
        public void onJobCreated(int jobId);
    }

    private JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    private JobCreateListener listener;

    private StaticDataRepository staticData = StaticDataRepository.getRepository();

    private CheckBoxPanel profilersPanel = new CheckBoxPanel();
    private ControlTypeSelect controlTypeSelect = new ControlTypeSelect();
    protected TestSelector testSelector = new TestSelector();
    private RadioChooser rebootBefore = new RadioChooser();
    private RadioChooser rebootAfter = new RadioChooser();
    private HostSelector hostSelector;

    private boolean controlEdited = false;
    private boolean controlReadyForSubmit = false;
    private JSONArray dependencies = new JSONArray();

    private Display display;

    public void bindDisplay(Display display) {
        this.display = display;
    }

    public CreateJobViewPresenter(JobCreateListener listener) {
        this.listener = listener;
    }

    public void cloneJob(JSONValue cloneInfo) {
        // reset() fires the TestSelectorListener, which will generate a new control file. We do
        // no want this, so we'll stop listening to it for a bit.
        testSelector.setListener(null);
        reset();
        testSelector.setListener(this);

        disableInputs();
        openControlFileEditor();
        JSONObject cloneObject = cloneInfo.isObject();
        JSONObject jobObject = cloneObject.get("job").isObject();

        display.getJobName().setText(jobObject.get("name").isString().stringValue());

        String priority = jobObject.get("priority").isString().stringValue();
        display.getPriorityList().selectByName(priority);

        display.getTimeout().setText(Utils.jsonToString(jobObject.get("timeout")));
        display.getMaxRuntime().setText(Utils.jsonToString(jobObject.get("max_runtime_hrs")));
        display.getEmailList().setText(
                jobObject.get("email_list").isString().stringValue());

        display.getSkipVerify().setValue(!jobObject.get("run_verify").isBoolean().booleanValue());
        rebootBefore.setSelectedChoice(Utils.jsonToString(jobObject.get("reboot_before")));
        rebootAfter.setSelectedChoice(Utils.jsonToString(jobObject.get("reboot_after")));
        display.getParseFailedRepair().setValue(
                jobObject.get("parse_failed_repair").isBoolean().booleanValue());
        display.getReserveHosts().setValue(jobObject.get("reserve_hosts").isBoolean().booleanValue());
        display.getHostless().setValue(cloneObject.get("hostless").isBoolean().booleanValue());

        if (display.getHostless().getValue()) {
            hostSelector.setEnabled(false);
        }
        if (staticData.getData("drone_sets_enabled").isBoolean().booleanValue()) {
            if (cloneObject.get("drone_set").isNull() == null) {
                display.getDroneSet().selectByName(Utils.jsonToString(cloneObject.get("drone_set")));
            }
        }

        controlTypeSelect.setControlType(
                jobObject.get("control_type").isString().stringValue());
        display.getSynchCountInput().setText(Utils.jsonToString(jobObject.get("synch_count")));
        setSelectedDependencies(jobObject.get("dependencies").isArray());
        display.getControlFile().setText(
                jobObject.get("control_file").isString().stringValue());
        controlReadyForSubmit = true;

        JSONArray hostInfo = cloneObject.get("hosts").isArray();
        List<String> hostnames = new ArrayList<String>();
        List<String> profiles = new ArrayList<String>();
        for (JSONObject host : new JSONArrayList<JSONObject>(hostInfo)) {
            hostnames.add(Utils.jsonToString(host.get("hostname")));
            profiles.add(Utils.jsonToString(host.get("profile")));
        }
        hostSelector.setSelectedHostnames(hostnames, profiles, true);

        JSONArray metaHostInfo = cloneObject.get("meta_hosts").isArray();

	for (JSONObject metaHost : new JSONArrayList<JSONObject>(metaHostInfo)) {
            hostSelector.addMetaHosts(Utils.jsonToString(metaHost.get("name")),
				      Utils.jsonToString(metaHost.get("count")),
				      Utils.jsonToString(metaHost.get("profile")));
        }

        hostSelector.refresh();
    }

    private void openControlFileEditor() {
        display.getControlFile().setReadOnly(false);
        display.getEditControlButton().setText(UNEDIT_CONTROL_STRING);
        display.setControlFilePanelOpen(true);
        controlTypeSelect.setEnabled(true);
        display.getSynchCountInput().setEnabled(true);
        display.getEditControlButton().setEnabled(true);
    }

    private void populatePriorities(JSONArray priorities) {
        for(int i = 0; i < priorities.size(); i++) {
            JSONArray priorityData = priorities.get(i).isArray();
            String priority = priorityData.get(1).isString().stringValue();
            display.getPriorityList().addItem(priority, priority);
        }

        resetPriorityToDefault();
    }

    private void resetPriorityToDefault() {
        JSONValue defaultValue = staticData.getData("default_priority");
        String defaultPriority = defaultValue.isString().stringValue();
        display.getPriorityList().selectByName(defaultPriority);
    }

    private void populateProfilers() {
        JSONArray tests = staticData.getData("profilers").isArray();

        for(JSONObject profiler : new JSONArrayList<JSONObject>(tests)) {
            String name = profiler.get("name").isString().stringValue();
            ICheckBox checkbox = profilersPanel.generateCheckBox();
            checkbox.setText(name);
            checkbox.addClickHandler(new ClickHandler() {
                public void onClick(ClickEvent event) {
                    updateNonProfiledRunControl();
                    generateControlFile(false);
                    setInputsEnabled();
                }
            });
            profilersPanel.add(checkbox);
        }

        display.getRunNonProfiledIteration().addClickHandler(new ClickHandler() {
            @Override
            public void onClick(ClickEvent event) {
                generateControlFile(false);
            }
        });
        // default to checked -- run a non-profiled iteration by default
        display.getRunNonProfiledIteration().setValue(true);
    }

    private void updateNonProfiledRunControl() {
        boolean anyProfilersChecked = !profilersPanel.getChecked().isEmpty();
        display.getRunNonProfiledIteration().setVisible(anyProfilersChecked);
    }

    private void populateRebootChoices() {
        AfeUtils.populateRadioChooser(rebootBefore, "reboot_before");
        AfeUtils.populateRadioChooser(rebootAfter, "reboot_after");
    }


    private JSONArray getKernelParams(String kernel_list, String cmdline) {
        JSONArray result = new JSONArray();

        for(String version: kernel_list.split("[, ]+")) {
            Map<String, String> item = new HashMap<String, String>();

            item.put("version", version);
            // if there is a cmdline part, put it for all versions in the map
            if (cmdline.length() > 0) {
                item.put("cmdline", cmdline);
            }

            result.set(result.size(), Utils.mapToJsonObject(item));
        }

        return result;
    }
    /**
     * Get parameters to submit to the generate_control_file RPC.
     * @param readyForSubmit are we getting a control file that's ready to submit for a job, or just
     * an intermediate control file to be viewed by the user?
     */
    protected JSONObject getControlFileParams(boolean readyForSubmit) {
        JSONObject params = new JSONObject();

        String kernelString = display.getKernel().getText();
        if (!kernelString.equals("")) {
            params.put(
                    "kernel", getKernelParams(kernelString, display.getKernelCmdline().getText()));
        }

        JSONArray tests = new JSONArray();
        for (JSONObject test : testSelector.getSelectedTests()) {
            tests.set(tests.size(), test.get("id"));
        }

        JSONArray profilers = new JSONArray();
        for (ICheckBox profiler : profilersPanel.getChecked()) {
            profilers.set(profilers.size(), new JSONString(profiler.getText()));
        }

        params.put("tests", tests);
        params.put("profilers", profilers);

        if (display.getRunNonProfiledIteration().isVisible()) {
            boolean profileOnly = !display.getRunNonProfiledIteration().getValue();
            params.put("profile_only", JSONBoolean.getInstance(profileOnly));
        }

        return params;
    }

    private void generateControlFile(final boolean readyForSubmit,
                                       final SimpleCallback finishedCallback,
                                       final SimpleCallback errorCallback) {
        JSONObject params = getControlFileParams(readyForSubmit);
        rpcProxy.rpcCall("generate_control_file", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                JSONObject controlInfo = result.isObject();
                String controlFileText = controlInfo.get("control_file").isString().stringValue();
                boolean isServer = controlInfo.get("is_server").isBoolean().booleanValue();
                String synchCount = Utils.jsonToString(controlInfo.get("synch_count"));
                setSelectedDependencies(controlInfo.get("dependencies").isArray());
                display.getControlFile().setText(controlFileText);
                controlTypeSelect.setControlType(isServer ? TestSelector.SERVER_TYPE :
                                                            TestSelector.CLIENT_TYPE);
                display.getSynchCountInput().setText(synchCount);
                controlReadyForSubmit = readyForSubmit;
                if (finishedCallback != null) {
                    finishedCallback.doCallback(this);
                }
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                if (errorCallback != null) {
                    errorCallback.doCallback(this);
                }
            }
        });
    }

    protected void generateControlFile(boolean readyForSubmit) {
        generateControlFile(readyForSubmit, null, null);
    }

    public void handleSkipVerify() {
        boolean shouldSkipVerify = false;
        for (JSONObject test : testSelector.getSelectedTests()) {
            boolean runVerify = test.get("run_verify").isBoolean().booleanValue();
            if (!runVerify) {
                shouldSkipVerify = true;
                break;
            }
        }

        if (shouldSkipVerify) {
            display.getSkipVerify().setValue(true);
            display.getSkipVerify().setEnabled(false);
        } else {
            display.getSkipVerify().setEnabled(true);
        }
    }

    protected void setInputsEnabled() {
        testSelector.setEnabled(true);
        profilersPanel.setEnabled(true);
        handleSkipVerify();
        display.getKernel().setEnabled(true);
        display.getKernelCmdline().setEnabled(true);
    }

    protected void disableInputs() {
        testSelector.setEnabled(false);
        profilersPanel.setEnabled(false);
        display.getKernel().setEnabled(false);
        display.getKernelCmdline().setEnabled(false);
    }

    public void initialize() {
        profilersPanel.bindDisplay(display.getCheckBoxPanelDisplay());
        controlTypeSelect.bindDisplay(display.getControlTypeSelectDisplay());
        testSelector.bindDisplay(display.getTestSelectorDisplay());
        rebootBefore.bindDisplay(display.getRebootBefore());
        rebootAfter.bindDisplay(display.getRebootAfter());

        display.getEditControlButton().setText(EDIT_CONTROL_STRING);
        display.getViewLink().setText(VIEW_CONTROL_STRING);

        hostSelector = new HostSelector();
        hostSelector.initialize();
        hostSelector.bindDisplay(display.getHostSelectorDisplay());

        populatePriorities(staticData.getData("priorities").isArray());

        BlurHandler kernelBlurHandler = new BlurHandler() {
            public void onBlur(BlurEvent event) {
                generateControlFile(false);
            }
        };

        display.getKernel().addBlurHandler(kernelBlurHandler);
        display.getKernelCmdline().addBlurHandler(kernelBlurHandler);

        KeyPressHandler kernelKeyPressHandler = new KeyPressHandler() {
            public void onKeyPress(KeyPressEvent event) {
                if (event.getCharCode() == (char) KeyCodes.KEY_ENTER) {
                    generateControlFile(false);
                }
            }
        };

        display.getKernel().addKeyPressHandler(kernelKeyPressHandler);
        display.getKernelCmdline().addKeyPressHandler(kernelKeyPressHandler);

        populateProfilers();
        updateNonProfiledRunControl();

        populateRebootChoices();
        onPreferencesChanged();

        if (parameterizedJobsEnabled()) {
            display.getEditControlButton().setEnabled(false);
        }

        display.getEditControlButton().addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                DOM.eventCancelBubble(DOM.eventGetCurrentEvent(), true);

                if (display.getEditControlButton().getText().equals(EDIT_CONTROL_STRING)) {
                    disableInputs();
                    display.getEditControlButton().setEnabled(false);
                    SimpleCallback onGotControlFile = new SimpleCallback() {
                        public void doCallback(Object source) {
                            openControlFileEditor();
                        }
                    };
                    SimpleCallback onControlFileError = new SimpleCallback() {
                        public void doCallback(Object source) {
                            setInputsEnabled();
                            display.getEditControlButton().setEnabled(true);
                        }
                    };
                    generateControlFile(true, onGotControlFile, onControlFileError);
                }
                else {
                    if (controlEdited &&
                        !Window.confirm("Are you sure you want to revert your" +
                                        " changes?")) {
                        return;
                    }
                    generateControlFile(false);
                    display.getControlFile().setReadOnly(true);
                    setInputsEnabled();
                    display.getEditControlButton().setText(EDIT_CONTROL_STRING);
                    controlTypeSelect.setEnabled(false);
                    display.getSynchCountInput().setEnabled(false);
                    controlEdited = false;
                }
            }
        });

        display.getControlFile().addChangeHandler(new ChangeHandler() {
            public void onChange(ChangeEvent event) {
                controlEdited = true;
            }
        });

        display.getControlFilePanelClose().addCloseHandler(new CloseHandler<DisclosurePanel>() {
            public void onClose(CloseEvent<DisclosurePanel> event) {
                display.getViewLink().setText(VIEW_CONTROL_STRING);
            }
        });

        display.getControlFilePanelOpen().addOpenHandler(new OpenHandler<DisclosurePanel>() {
            public void onOpen(OpenEvent<DisclosurePanel> event) {
                display.getViewLink().setText(HIDE_CONTROL_STRING);
            }
        });

        display.getSubmitJobButton().addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                submitJob(false);
            }
        });

        display.getCreateTemplateJobButton().addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                submitJob(true);
            }
        });

        display.getResetButton().addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                reset();
            }
        });

        display.getHostless().addClickHandler(new ClickHandler() {
            @Override
            public void onClick(ClickEvent event) {
                hostSelector.setEnabled(!display.getHostless().getValue());
            }
        });

        reset();

        if (staticData.getData("drone_sets_enabled").isBoolean().booleanValue()) {
            AfeUtils.populateListBox(display.getDroneSet(), "drone_sets");
        } else {
            AfeUtils.removeElement("create_drone_set_wrapper");
        }

        testSelector.setListener(this);
    }

    public void reset() {
        StaticDataRepository repository = StaticDataRepository.getRepository();

        display.getJobName().setText("");
        resetPriorityToDefault();
        rebootBefore.reset();
        rebootAfter.reset();
        display.getParseFailedRepair().setValue(
                repository.getData("parse_failed_repair_default").isBoolean().booleanValue());
        display.getHostless().setValue(false);
        display.getReserveHosts().setValue(false);
        display.getKernel().setText("");
        display.getKernelCmdline().setText("");
        display.getTimeout().setText(Utils.jsonToString(repository.getData("job_timeout_default")));
        display.getMaxRuntime().setText(
                Utils.jsonToString(repository.getData("job_max_runtime_hrs_default")));
        display.getEmailList().setText("");
        testSelector.reset();
        display.getSkipVerify().setValue(false);
        profilersPanel.reset();
        setInputsEnabled();
        controlTypeSelect.setControlType(TestSelector.CLIENT_TYPE);
        controlTypeSelect.setEnabled(false);
        display.getSynchCountInput().setEnabled(false);
        display.getSynchCountInput().setText("1");
        display.getControlFile().setText("");
        display.getControlFile().setReadOnly(true);
        controlEdited = false;
        display.setControlFilePanelOpen(false);
        display.getEditControlButton().setText(EDIT_CONTROL_STRING);
        hostSelector.reset();
        dependencies = new JSONArray();
    }

    private void submitJob(final boolean isTemplate) {
        final int timeoutValue, maxRuntimeValue;
        final JSONValue synchCount;
        try {
            timeoutValue = parsePositiveIntegerInput(display.getTimeout().getText(), "timeout");
            maxRuntimeValue = parsePositiveIntegerInput(
                    display.getMaxRuntime().getText(), "max runtime");

            if (display.getHostless().getValue()) {
                synchCount = JSONNull.getInstance();
            } else {
                synchCount = new JSONNumber(parsePositiveIntegerInput(
                    display.getSynchCountInput().getText(),
                    "number of machines used per execution"));
            }
        } catch (IllegalArgumentException exc) {
            return;
        }

        // disallow accidentally clicking submit twice
        display.getSubmitJobButton().setEnabled(false);

        final SimpleCallback doSubmit = new SimpleCallback() {
            public void doCallback(Object source) {
                JSONObject args = new JSONObject();
                args.put("name", new JSONString(display.getJobName().getText()));
                String priority = display.getPriorityList().getSelectedName();
                args.put("priority", new JSONString(priority));
                args.put("control_file", new JSONString(display.getControlFile().getText()));
                args.put("control_type",
                         new JSONString(controlTypeSelect.getControlType()));
                args.put("synch_count", synchCount);
                args.put("timeout", new JSONNumber(timeoutValue));
                args.put("max_runtime_hrs", new JSONNumber(maxRuntimeValue));
                args.put("email_list", new JSONString(display.getEmailList().getText()));
                args.put("run_verify", JSONBoolean.getInstance(
                        !display.getSkipVerify().getValue()));
                args.put("is_template", JSONBoolean.getInstance(isTemplate));
                args.put("dependencies", getSelectedDependencies());
                args.put("reboot_before", new JSONString(rebootBefore.getSelectedChoice()));
                args.put("reboot_after", new JSONString(rebootAfter.getSelectedChoice()));
                args.put("parse_failed_repair",
                         JSONBoolean.getInstance(display.getParseFailedRepair().getValue()));
                args.put("hostless", JSONBoolean.getInstance(display.getHostless().getValue()));
                args.put("reserve_hosts", JSONBoolean.getInstance(display.getReserveHosts().getValue()));

                if (staticData.getData("drone_sets_enabled").isBoolean().booleanValue()) {
                    args.put("drone_set", new JSONString(display.getDroneSet().getSelectedName()));
                }

                HostSelector.HostSelection hosts = hostSelector.getSelectedHosts();
                args.put("hosts", Utils.stringsToJSON(hosts.hosts));
                args.put("profiles", Utils.stringsToJSON(hosts.profiles));
                args.put("meta_hosts", Utils.stringsToJSON(hosts.metaHosts));
                args.put("meta_host_profiles", Utils.stringsToJSON(hosts.metaHostProfiles));
                args.put("one_time_hosts",
                    Utils.stringsToJSON(hosts.oneTimeHosts));

                rpcProxy.rpcCall("create_job", args, new JsonRpcCallback() {
                    @Override
                    public void onSuccess(JSONValue result) {
                        int id = (int) result.isNumber().doubleValue();
                        NotifyManager.getInstance().showMessage(
                                    "Job " + Integer.toString(id) + " created");
                        reset();
                        if (listener != null) {
                            listener.onJobCreated(id);
                        }
                        display.getSubmitJobButton().setEnabled(true);
                    }

                    @Override
                    public void onError(JSONObject errorObject) {
                        super.onError(errorObject);
                        display.getSubmitJobButton().setEnabled(true);
                    }
                });
            }
        };

        // ensure control file is ready for submission
        if (!controlReadyForSubmit) {
            generateControlFile(true, doSubmit, new SimpleCallback() {
                public void doCallback(Object source) {
                    display.getSubmitJobButton().setEnabled(true);
                }
            });
        } else {
            doSubmit.doCallback(this);
        }
    }

    private JSONArray getSelectedDependencies() {
        return dependencies;
    }

    private void setSelectedDependencies(JSONArray dependencies) {
        this.dependencies = dependencies;
    }

    private int parsePositiveIntegerInput(String input, String fieldName) {
        final int parsedInt;
        try {
            if (input.equals("") ||
                (parsedInt = Integer.parseInt(input)) <= 0) {
                    String error = "Please enter a positive " + fieldName;
                    NotifyManager.getInstance().showError(error);
                    throw new IllegalArgumentException();
            }
        } catch (NumberFormatException e) {
            String error = "Invalid " + fieldName + ": \"" + input + "\"";
            NotifyManager.getInstance().showError(error);
            throw new IllegalArgumentException();
        }
        return parsedInt;
    }

    public void refresh() {
        hostSelector.refresh();
    }

    public void onTestSelectionChanged() {
        generateControlFile(false);
        setInputsEnabled();
    }

    private void setRebootSelectorDefault(RadioChooser chooser, String name) {
        JSONObject user = staticData.getData("current_user").isObject();
        String defaultOption = Utils.jsonToString(user.get(name));
        chooser.setDefaultChoice(defaultOption);
    }

    private void selectPreferredDroneSet() {
        JSONObject user = staticData.getData("current_user").isObject();
        JSONValue droneSet = user.get("drone_set");
        if (droneSet.isNull() == null) {
            String preference = Utils.jsonToString(user.get("drone_set"));
            display.getDroneSet().selectByName(preference);
        }
    }

    public void onPreferencesChanged() {
        setRebootSelectorDefault(rebootBefore, "reboot_before");
        setRebootSelectorDefault(rebootAfter, "reboot_after");
        selectPreferredDroneSet();
        testSelector.reset();
    }

    private boolean parameterizedJobsEnabled() {
        return staticData.getData("parameterized_jobs").isBoolean().booleanValue();
    }
}
