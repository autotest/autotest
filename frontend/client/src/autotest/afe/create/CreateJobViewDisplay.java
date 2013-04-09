package autotest.afe.create;

import autotest.afe.CheckBoxPanel;
import autotest.afe.CheckBoxPanelDisplay;
import autotest.afe.ControlTypeSelect;
import autotest.afe.ControlTypeSelectDisplay;
import autotest.afe.HostSelector;
import autotest.afe.HostSelectorDisplay;
import autotest.afe.IButton;
import autotest.afe.IButton.ButtonImpl;
import autotest.afe.ICheckBox;
import autotest.afe.ICheckBox.CheckBoxImpl;
import autotest.afe.ITextArea;
import autotest.afe.ITextArea.TextAreaImpl;
import autotest.afe.ITextBox;
import autotest.afe.ITextBox.TextBoxImpl;
import autotest.afe.TestSelector;
import autotest.afe.TestSelectorDisplay;
import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.RadioChooser;
import autotest.common.ui.RadioChooserDisplay;
import autotest.common.ui.SimplifiedList;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.logical.shared.HasCloseHandlers;
import com.google.gwt.event.logical.shared.HasOpenHandlers;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.DisclosurePanel;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasValue;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;

public class CreateJobViewDisplay implements CreateJobViewPresenter.Display {
    public static final int CHECKBOX_PANEL_COLUMNS = 5;

    private TextBox jobName = new TextBox();
    private ExtendedListBox priorityList = new ExtendedListBox();
    private TextBoxImpl kernel = new TextBoxImpl();
    private TextBoxImpl kernel_cmdline = new TextBoxImpl();
    private TextBox timeout = new TextBox();
    private TextBox maxRuntime = new TextBox();
    private TextBox emailList = new TextBox();
    private CheckBoxImpl skipVerify = new CheckBoxImpl();
    private RadioChooserDisplay rebootBefore = new RadioChooserDisplay();
    private RadioChooserDisplay rebootAfter = new RadioChooserDisplay();
    private CheckBox parseFailedRepair = new CheckBox();
    private CheckBoxImpl hostless = new CheckBoxImpl();
    private CheckBox reserveHosts = new CheckBox();
    private TestSelectorDisplay testSelector = new TestSelectorDisplay();
    private CheckBoxPanelDisplay profilersPanel = new CheckBoxPanelDisplay(CHECKBOX_PANEL_COLUMNS);
    private CheckBoxImpl runNonProfiledIteration =
        new CheckBoxImpl("Run each test without profilers first");
    private ExtendedListBox droneSet = new ExtendedListBox();
    private TextAreaImpl controlFile = new TextAreaImpl();
    private DisclosurePanel controlFilePanel = new DisclosurePanel();
    private ControlTypeSelectDisplay controlTypeSelect = new ControlTypeSelectDisplay();
    private TextBoxImpl synchCountInput = new TextBoxImpl();
    private ButtonImpl editControlButton = new ButtonImpl();
    private HostSelectorDisplay hostSelector = new HostSelectorDisplay();
    private ButtonImpl submitJobButton = new ButtonImpl("Submit Job");
    private Button createTemplateJobButton = new Button("Create Template Job");
    private Button resetButton = new Button("Reset");
    private Anchor viewLink = new Anchor("");

    public void initialize(HTMLPanel panel) {
        Panel profilerControls = new VerticalPanel();
        profilerControls.add(profilersPanel);
        profilerControls.add(runNonProfiledIteration);

        controlFile.setSize("50em", "30em");

        HorizontalPanel controlOptionsPanel = new HorizontalPanel();
        controlOptionsPanel.setVerticalAlignment(HorizontalPanel.ALIGN_BOTTOM);
        controlOptionsPanel.add(controlTypeSelect);
        Label useLabel = new Label("Use");
        useLabel.getElement().getStyle().setProperty("marginLeft", "1em");
        synchCountInput.setSize("3em", ""); // set width only
        synchCountInput.getElement().getStyle().setProperty("margin", "0 0.5em 0 0.5em");
        controlOptionsPanel.add(useLabel);
        controlOptionsPanel.add(synchCountInput);
        controlOptionsPanel.add(new Label("host(s) per execution"));
        Panel controlEditPanel = new VerticalPanel();
        controlEditPanel.add(controlOptionsPanel);
        controlEditPanel.add(controlFile);

        Panel controlHeaderPanel = new HorizontalPanel();
        controlHeaderPanel.add(viewLink);
        controlHeaderPanel.add(editControlButton);

        controlFilePanel.setHeader(controlHeaderPanel);
        controlFilePanel.add(controlEditPanel);

        panel.add(jobName, "create_job_name");
        panel.add(kernel, "create_kernel");
        panel.add(kernel_cmdline, "create_kernel_cmdline");
        panel.add(timeout, "create_timeout");
        panel.add(maxRuntime, "create_max_runtime");
        panel.add(emailList, "create_email_list");
        panel.add(priorityList, "create_priority");
        panel.add(skipVerify, "create_skip_verify");
        panel.add(rebootBefore, "create_reboot_before");
        panel.add(rebootAfter, "create_reboot_after");
        panel.add(parseFailedRepair, "create_parse_failed_repair");
        panel.add(hostless, "create_hostless");
        panel.add(reserveHosts, "reserve_hosts");
        panel.add(testSelector, "create_tests");
        panel.add(profilerControls, "create_profilers");
        panel.add(controlFilePanel, "create_edit_control");
        panel.add(hostSelector, "create_host_selector");
        panel.add(submitJobButton, "create_submit");
        panel.add(createTemplateJobButton, "create_template_job");
        panel.add(resetButton, "create_reset");
        panel.add(droneSet, "create_drone_set");
    }

    public CheckBoxPanel.Display getCheckBoxPanelDisplay() {
        return profilersPanel;
    }

    public ControlTypeSelect.Display getControlTypeSelectDisplay() {
        return controlTypeSelect;
    }

    public ITextArea getControlFile() {
        return controlFile;
    }

    public HasCloseHandlers<DisclosurePanel> getControlFilePanelClose() {
        return controlFilePanel;
    }

    public HasOpenHandlers<DisclosurePanel> getControlFilePanelOpen() {
        return controlFilePanel;
    }

    public HasClickHandlers getCreateTemplateJobButton() {
        return createTemplateJobButton;
    }

    public SimplifiedList getDroneSet() {
        return droneSet;
    }

    public IButton getEditControlButton() {
        return editControlButton;
    }

    public HasText getEmailList() {
        return emailList;
    }

    public HostSelector.Display getHostSelectorDisplay() {
        return hostSelector;
    }

    public ICheckBox getHostless() {
        return hostless;
    }

    public HasText getJobName() {
        return jobName;
    }

    public ITextBox getKernel() {
        return kernel;
    }

    public ITextBox getKernelCmdline() {
        return kernel_cmdline;
    }

    public HasText getMaxRuntime() {
        return maxRuntime;
    }

    public HasValue<Boolean> getParseFailedRepair() {
        return parseFailedRepair;
    }

    public HasValue<Boolean> getReserveHosts() {
        return reserveHosts;
    }

    public SimplifiedList getPriorityList() {
        return priorityList;
    }

    public RadioChooser.Display getRebootAfter() {
        return rebootAfter;
    }

    public RadioChooser.Display getRebootBefore() {
        return rebootBefore;
    }

    public HasClickHandlers getResetButton() {
        return resetButton;
    }

    public ICheckBox getRunNonProfiledIteration() {
        return runNonProfiledIteration;
    }

    public ICheckBox getSkipVerify() {
        return skipVerify;
    }

    public IButton getSubmitJobButton() {
        return submitJobButton;
    }

    public ITextBox getSynchCountInput() {
        return synchCountInput;
    }

    public TestSelector.Display getTestSelectorDisplay() {
        return testSelector;
    }

    public HasText getTimeout() {
        return timeout;
    }

    public HasText getViewLink() {
        return viewLink;
    }

    public void setControlFilePanelOpen(boolean isOpen) {
        controlFilePanel.setOpen(isOpen);
    }
}
