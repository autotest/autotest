package autotest.tko;

import autotest.common.SimpleCallback;
import autotest.common.Utils;
import autotest.common.ui.NotifyManager;
import autotest.tko.TkoUtils.FieldInfo;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.PopupPanel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;
import com.google.gwt.user.client.ui.PopupPanel.PositionCallback;

import java.util.HashSet;
import java.util.Map;
import java.util.Set;

class CommonPanel extends Composite implements ClickHandler, PositionCallback {
    private static final String WIKI_URL = "http://autotest.kernel.org/wiki/TkoHowTo";
    private static final String SHOW_QUICK_REFERENCE = "Show quick reference";
    private static final String HIDE_QUICK_REFERENCE = "Hide quick reference";
    private static final String SHOW_CONTROLS = "Show controls";
    private static final String HIDE_CONTROLS = "Hide controls";

    private static CommonPanel theInstance = new CommonPanel();

    private String savedSqlCondition;
    private boolean savedShowInvalid = false;
    private HeaderFieldCollection headerFields = new HeaderFieldCollection();

    private ParameterizedFieldListPresenter parameterizedFieldPresenter =
        new ParameterizedFieldListPresenter(headerFields);

    private HTMLPanel htmlPanel;
    private TextArea customSqlBox = new TextArea();
    private CheckBox showInvalid = new CheckBox("Show invalidated tests");
    private Anchor quickReferenceLink = new Anchor(SHOW_QUICK_REFERENCE);
    private PopupPanel quickReferencePopup;
    private Anchor showHideControlsLink = new Anchor(HIDE_CONTROLS);
    private Panel allControlsPanel = RootPanel.get("common_all_controls");
    private Set<CommonPanelListener> listeners = new HashSet<CommonPanelListener>();
    private ParameterizedFieldListDisplay parameterizedFieldDisplay =
        new ParameterizedFieldListDisplay();


    public static interface CommonPanelListener {
        /**
         * Called to show or hide tab-specific controls.
         */
        public void onSetControlsVisible(boolean visible);

        /**
         * Called when the set of HeaderFields has changed.
         */
        public void onFieldsChanged();
    }

    private CommonPanel() {
        htmlPanel = Utils.divToPanel("common_panel");
        initWidget(htmlPanel);
    }

    public void initialize() {
        customSqlBox.setSize("50em", "5em");
        quickReferenceLink.addClickHandler(this);
        showHideControlsLink.addClickHandler(this);

        Panel titlePanel = new HorizontalPanel();
        titlePanel.add(getFieldLabel("Custom fields:"));
        titlePanel.add(new HTML("&nbsp;<a href=\"" + Utils.escape(WIKI_URL) + "#custom_fields\" " +
                                "target=\"_blank\">[?]</a>"));
        Panel attributeFilters = new VerticalPanel();
        attributeFilters.setStyleName("box");
        attributeFilters.add(titlePanel);
        attributeFilters.add(parameterizedFieldDisplay);

        Panel commonFilterPanel = new VerticalPanel();
        commonFilterPanel.add(customSqlBox);
        commonFilterPanel.add(attributeFilters);
        commonFilterPanel.add(showInvalid);
        htmlPanel.add(commonFilterPanel, "common_filters");
        htmlPanel.add(quickReferenceLink, "common_quick_reference");
        htmlPanel.add(showHideControlsLink, "common_show_hide_controls");
        generateQuickReferencePopup();

        headerFields.populateFromList("all_fields");
        notifyOnFieldsChanged();

        parameterizedFieldPresenter.bindDisplay(parameterizedFieldDisplay);
        parameterizedFieldPresenter.setListener(new SimpleCallback() {
            @Override
            public void doCallback(Object source) {
                notifyOnFieldsChanged();
            }
        });
    }

    private Widget getFieldLabel(String string) {
        Label label = new Label(string);
        label.setStyleName("field-name");
        return label;
    }

    public static CommonPanel getPanel() {
        return theInstance;
    }

    /**
     * For testability.
     */
    public static void setInstance(CommonPanel panel) {
        theInstance = panel;
    }

    public void setConditionVisible(boolean visible) {
        Utils.setElementVisible("common_condition_div", visible);
    }

    public void setSqlCondition(String text) {
        savedSqlCondition = text;
    }

    public boolean isViewReadyForQuery() {
        if (customSqlBox.getText().trim().equals("")) {
            NotifyManager.getInstance().showError("Global filter cannot be empty");
            return false;
        }

        return true;
    }

    public void updateStateFromView() {
        savedSqlCondition = customSqlBox.getText().trim();
        savedShowInvalid = showInvalid.getValue();
    }

    public void updateViewFromState() {
        customSqlBox.setText(savedSqlCondition);
        showInvalid.setValue(savedShowInvalid);
    }

    public JSONObject getConditionArgs() {
        String condition = savedSqlCondition;
        if (!savedShowInvalid) {
            parameterizedFieldPresenter.addFieldIfNotPresent(TestLabelField.TYPE_NAME,
                                                             "invalidated");
            condition = "(" + condition + ") AND test_label_invalidated.id IS NULL";
        }

        JSONObject conditionArgs = new JSONObject();
        addIfNonempty(conditionArgs, "extra_where", condition);
        for (HeaderField field : headerFields) {
            field.addQueryParameters(conditionArgs);
        }

        return conditionArgs;
    }

    private void addIfNonempty(JSONObject conditionArgs, String key, String value) {
        if (value.equals("")) {
            return;
        }
        conditionArgs.put(key, new JSONString(value));
    }

    public void refineCondition(String newCondition) {
        setSqlCondition(TkoUtils.joinWithParens(" AND ", savedSqlCondition, newCondition));
    }

    public void refineCondition(TestSet tests) {
        refineCondition(tests.getPartialSqlCondition());
    }

    public void handleHistoryArguments(Map<String, String> arguments) {
        setSqlCondition(arguments.get("condition"));
        savedShowInvalid = Boolean.valueOf(arguments.get("show_invalid"));
        parameterizedFieldPresenter.handleHistoryArguments(arguments);
        updateViewFromState();
    }

    public void addHistoryArguments(Map<String, String> arguments) {
        arguments.put("condition", savedSqlCondition);
        arguments.put("show_invalid", Boolean.toString(savedShowInvalid));
        parameterizedFieldPresenter.addHistoryArguments(arguments);
    }

    public void fillDefaultHistoryValues(Map<String, String> arguments) {
        Utils.setDefaultValue(arguments, "condition", "");
        Utils.setDefaultValue(arguments, "show_invalid", Boolean.toString(savedShowInvalid));
    }

    public void onClick(ClickEvent event) {
        if (event.getSource() == quickReferenceLink) {
            handleQuickReferenceClick();
        } else {
            assert event.getSource() == showHideControlsLink;
            handleShowHideControlsClick();
        }
    }

    private void handleShowHideControlsClick() {
        boolean areControlsVisible = showHideControlsLink.getText().equals(SHOW_CONTROLS);
        allControlsPanel.setVisible(areControlsVisible);
        showHideControlsLink.setText(areControlsVisible ? HIDE_CONTROLS : SHOW_CONTROLS);
        for (CommonPanelListener listener : listeners) {
            listener.onSetControlsVisible(areControlsVisible);
        }
    }

    private void handleQuickReferenceClick() {
        if (isQuickReferenceShowing()) {
            quickReferencePopup.hide();
            quickReferenceLink.setText(SHOW_QUICK_REFERENCE);
        } else {
            quickReferencePopup.setPopupPositionAndShow(this);
            quickReferenceLink.setText(HIDE_QUICK_REFERENCE);
        }
    }

    private boolean isQuickReferenceShowing() {
        return quickReferenceLink.getText().equals(HIDE_QUICK_REFERENCE);
    }

    private void generateQuickReferencePopup() {
        FlexTable fieldTable = new FlexTable();
        fieldTable.setText(0, 0, "Name");
        fieldTable.setText(0, 1, "Field");
        fieldTable.getRowFormatter().setStyleName(0, "data-row-header");
        int row = 1;
        for (FieldInfo fieldInfo : TkoUtils.getFieldList("all_fields")) {
            fieldTable.setText(row, 0, fieldInfo.name);
            fieldTable.setText(row, 1, fieldInfo.field);
            row++;
        }
        quickReferencePopup = new PopupPanel(false);
        quickReferencePopup.add(fieldTable);
    }

    /**
     * PopupListener callback.
     */
    public void setPosition(int offsetWidth, int offsetHeight) {
        quickReferencePopup.setPopupPosition(
             customSqlBox.getAbsoluteLeft() + customSqlBox.getOffsetWidth(),
             customSqlBox.getAbsoluteTop());
    }

    public void addListener(CommonPanelListener listener) {
        listeners.add(listener);
    }

    public HeaderFieldCollection getHeaderFields() {
        return headerFields;
    }

    private void notifyOnFieldsChanged() {
        for (CommonPanelListener listener : listeners) {
            listener.onFieldsChanged();
        }
    }
}
