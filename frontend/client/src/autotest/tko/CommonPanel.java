package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.ElementWidget;
import autotest.common.ui.SimpleHyperlink;
import autotest.tko.TkoUtils.FieldInfo;
import autotest.tko.WidgetList.ListWidgetFactory;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.PopupPanel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;
import com.google.gwt.user.client.ui.PopupPanel.PositionCallback;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

class CommonPanel extends Composite implements ClickListener, PositionCallback {
    private static final String WIKI_URL = "http://autotest.kernel.org/wiki/TkoHowTo";
    private static final String SHOW_QUICK_REFERENCE = "Show quick reference";
    private static final String HIDE_QUICK_REFERENCE = "Hide quick reference";
    private static final String SHOW_CONTROLS = "Show controls";
    private static final String HIDE_CONTROLS = "Hide controls";
    private static final String INCLUDE_ATTRIBUTES_TABLE = "test_attributes_include";
    private static final String EXCLUDE_ATTRIBUTES_TABLE = "test_attributes_exclude";
    private static CommonPanel theInstance = new CommonPanel();
    
    private class AttributeFilter extends Composite implements ClickListener {
        private ListBox includeOrExclude = new ListBox();
        private TextBox attributeWhere = new TextBox(), valueWhere = new TextBox();
        
        public AttributeFilter() {
            includeOrExclude.addItem("Include");
            includeOrExclude.addItem("Exclude");
            
            Panel panel = new HorizontalPanel();
            panel.add(includeOrExclude);
            panel.add(new Label("tests with attribute"));
            panel.add(attributeWhere);
            panel.add(new Label("and value"));
            panel.add(valueWhere);
            
            SimpleHyperlink deleteLink = new SimpleHyperlink("[X]");
            deleteLink.addClickListener(this);
            panel.add(deleteLink);
            
            initWidget(panel);
        }

        public void onClick(Widget sender) {
            attributeFilterList.deleteWidget(this);
        }
        
        public boolean isInclude() {
            return includeOrExclude.getSelectedIndex() == 0;
        }
        
        public String getFilterString() {
            String tableName;
            if (isInclude()) {
                tableName = INCLUDE_ATTRIBUTES_TABLE;
            } else {
                tableName = EXCLUDE_ATTRIBUTES_TABLE;
            }
            
            return "(" + tableName + ".attribute " + attributeWhere.getText() + " AND " +
                   tableName + ".value " + valueWhere.getText() + ")";
        }
        
        public void addToHistory(Map<String, String> args, String prefix) {
            args.put(prefix + "_include", Boolean.toString(isInclude()));
            args.put(prefix + "_attribute", attributeWhere.getText());
            args.put(prefix + "_value", valueWhere.getText());
        }
    }
    
    private class AttributeFilterFactory implements ListWidgetFactory<AttributeFilter> {
        public AttributeFilter getNewWidget() {
            return new AttributeFilter();
        }
    }
    
    private TextArea customSqlBox = new TextArea();
    private CheckBox showInvalid = new CheckBox("Show invalidated tests");
    private SimpleHyperlink quickReferenceLink = new SimpleHyperlink(SHOW_QUICK_REFERENCE);
    private PopupPanel quickReferencePopup;
    private SimpleHyperlink showHideControlsLink = new SimpleHyperlink(HIDE_CONTROLS);
    private Panel allControlsPanel = RootPanel.get("common_all_controls");
    private boolean savedShowInvalid = false;
    private JSONObject savedCondition = new JSONObject();
    private Set<CommonPanelListener> listeners = new HashSet<CommonPanelListener>();
    private WidgetList<AttributeFilter> attributeFilterList;
    
    public static interface CommonPanelListener {
        public void onSetControlsVisible(boolean visible);
    }
    
    private CommonPanel() {
        ElementWidget panelElement = new ElementWidget("common_panel");
        initWidget(panelElement);
    }
    
    public void initialize() {
        customSqlBox.setSize("50em", "5em");
        quickReferenceLink.addClickListener(this);
        showHideControlsLink.addClickListener(this);
        
        attributeFilterList = 
            new WidgetList<AttributeFilter>(new AttributeFilterFactory(), "Add attribute filter");
        Panel titlePanel = new HorizontalPanel();
        titlePanel.add(getFieldLabel("Test attributes:"));
        titlePanel.add(new HTML("&nbsp;<a href=\"" + WIKI_URL + "#attribute_filtering\" " +
                                "target=\"_blank\">[?]</a>"));
        Panel attributeFilters = new VerticalPanel();
        attributeFilters.setStyleName("box");
        attributeFilters.add(titlePanel);
        attributeFilters.add(attributeFilterList);
        
        Panel commonFilterPanel = new VerticalPanel();
        commonFilterPanel.add(customSqlBox);
        commonFilterPanel.add(attributeFilters);
        commonFilterPanel.add(showInvalid);
        RootPanel.get("common_filters").add(commonFilterPanel);
        RootPanel.get("common_quick_reference").add(quickReferenceLink);
        RootPanel.get("common_show_hide_controls").add(showHideControlsLink);
        generateQuickReferencePopup();
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
        RootPanel.get("common_condition_div").setVisible(visible);
    }
    
    private String getSqlCondition() {
        return customSqlBox.getText().trim();
    }
    
    public void setSqlCondition(String text) {
        customSqlBox.setText(text);
        saveSqlCondition();
    }
    
    private void saveAttributeFilters() {
        List<String> include = new ArrayList<String>(), exclude = new ArrayList<String>();
        for (AttributeFilter filter : attributeFilterList.getWidgets()) {
            if (filter.isInclude()) {
                include.add(filter.getFilterString());
            } else {
                exclude.add(filter.getFilterString());
            }
        }
        
        String includeSql = Utils.joinStrings(" OR ", include);
        String excludeSql = Utils.joinStrings(" OR ", exclude);
        saveIfNonempty("include_attributes_where", includeSql);
        saveIfNonempty("exclude_attributes_where", excludeSql);
    }
    
    public void saveSqlCondition() {
        savedCondition = new JSONObject();
        saveIfNonempty("extra_where", getSqlCondition());
        saveAttributeFilters();
        
        savedShowInvalid = showInvalid.isChecked();
        if (!savedShowInvalid) {
            List<String> labelsToExclude = 
                Arrays.asList(new String[] {TestLabelManager.INVALIDATED_LABEL});
            savedCondition.put("exclude_labels", Utils.stringsToJSON(labelsToExclude));
        }
    }
    
    private void saveIfNonempty(String key, String value) {
        if (value.equals("")) {
            return;
        }
        savedCondition.put(key, new JSONString(value));
    }

    public JSONObject getSavedConditionArgs() {
        return Utils.copyJSONObject(savedCondition);
    }

    public void refineCondition(String newCondition) {
        String sqlCondition = TkoUtils.getSqlCondition(savedCondition);
        setSqlCondition(TkoUtils.joinWithParens(" AND ", sqlCondition, newCondition));
    }
    
    public void refineCondition(TestSet tests) {
        refineCondition(tests.getPartialSqlCondition());
    }
    
    private String getListKey(String base, int index) {
        return base + "_" + Integer.toString(index);
    }
    
    public AttributeFilter attributeFilterFromHistory(Map<String, String> args, String prefix) {
        String includeKey = prefix + "_include";
        if (!args.containsKey(includeKey)) {
            return null;
        }
        
        AttributeFilter filter = new AttributeFilter();
        boolean include = Boolean.valueOf(args.get(includeKey));
        filter.includeOrExclude.setSelectedIndex(include ? 0 : 1);
        filter.attributeWhere.setText(args.get(prefix + "_attribute"));
        filter.valueWhere.setText(args.get(prefix + "_value"));
        return filter;
    }

    public void handleHistoryArguments(Map<String, String> arguments) {
        setSqlCondition(arguments.get("condition"));
        savedShowInvalid = Boolean.valueOf(arguments.get("show_invalid"));
        showInvalid.setChecked(savedShowInvalid);
        
        attributeFilterList.clear();
        for (int index = 0; ; index++) {
            AttributeFilter filter = attributeFilterFromHistory(arguments,
                                                                getListKey("attribute", index));
            if (filter == null) {
                break;
            }
            attributeFilterList.addWidget(filter);
        }
    }
    
    public void addHistoryArguments(Map<String, String> arguments) {
        if (savedCondition.containsKey("extra_where")) {
            arguments.put("condition", savedCondition.get("extra_where").isString().stringValue());
        }
        arguments.put("show_invalid", Boolean.toString(savedShowInvalid));
        int index = 0;
        for (AttributeFilter filter : attributeFilterList.getWidgets()) {
            filter.addToHistory(arguments, getListKey("attribute", index));
            index++;
        }
    }

    public void fillDefaultHistoryValues(Map<String, String> arguments) {
        Utils.setDefaultValue(arguments, "condition", "");
        Utils.setDefaultValue(arguments, "show_invalid", Boolean.toString(savedShowInvalid));
    }

    public void onClick(Widget sender) {
        if (sender == quickReferenceLink) {
            handleQuickReferenceClick();
        } else {
            assert sender == showHideControlsLink;
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
}
