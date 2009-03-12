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
    
    private static class AttributeFilterData {
        private boolean isInclude;
        private String attributeWhere, valueWhere;

        public AttributeFilterData(boolean isInclude, String attributeWhere, String valueWhere) {
            this.isInclude = isInclude;
            this.attributeWhere = attributeWhere;
            this.valueWhere = valueWhere;
        }
        
        public boolean isInclude() {
            return isInclude;
        }

        private String getFilterString() {
            String tableName;
            if (isInclude) {
                tableName = INCLUDE_ATTRIBUTES_TABLE;
            } else {
                tableName = EXCLUDE_ATTRIBUTES_TABLE;
            }
            
            return "(" + tableName + ".attribute " + attributeWhere + " AND " +
                   tableName + ".value " + valueWhere + ")";
        }

        public void addToHistory(Map<String, String> args, String prefix) {
            args.put(prefix + "_include", Boolean.toString(isInclude()));
            args.put(prefix + "_attribute", attributeWhere);
            args.put(prefix + "_value", valueWhere);
        }
        
        public static AttributeFilterData fromHistory(Map<String, String> args, String prefix) {
            String includeKey = prefix + "_include";
            if (!args.containsKey(includeKey)) {
                return null;
            }
            
            boolean include = Boolean.valueOf(args.get(includeKey));
            String attributeWhere = args.get(prefix + "_attribute");
            String valueWhere = args.get(prefix + "_value");
            return new AttributeFilterData(include, attributeWhere, valueWhere);
        }
    }
    
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

        public AttributeFilterData getFilterData() {
            boolean isInclude = (includeOrExclude.getSelectedIndex() == 0);
            return new AttributeFilterData(isInclude, attributeWhere.getText(), 
                                           valueWhere.getText());
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
    private Set<CommonPanelListener> listeners = new HashSet<CommonPanelListener>();
    private WidgetList<AttributeFilter> attributeFilterList;

    private String savedSqlCondition;
    private boolean savedShowInvalid = false;
    private List<AttributeFilterData> savedAttributeFilters = new ArrayList<AttributeFilterData>();
    
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
    
    public void setSqlCondition(String text) {
        customSqlBox.setText(text);
        updateStateFromView();
    }
    
    public void updateStateFromView() {
        savedSqlCondition = customSqlBox.getText().trim();
        savedShowInvalid = showInvalid.isChecked();
        
        savedAttributeFilters.clear();
        for (AttributeFilter filter : attributeFilterList.getWidgets()) {
            savedAttributeFilters.add(filter.getFilterData());
        }
    }
    
    public AttributeFilter getFilterWidgetFromData(AttributeFilterData filterData) {
        AttributeFilter filter = new AttributeFilter();
        filter.includeOrExclude.setSelectedIndex(filterData.isInclude() ? 0 : 1);
        filter.attributeWhere.setText(filterData.attributeWhere);
        filter.valueWhere.setText(filterData.valueWhere);
        return filter;
    }
    
    public void updateViewFromState() {
        customSqlBox.setText(savedSqlCondition);
        showInvalid.setChecked(savedShowInvalid);
        
        attributeFilterList.clear();
        for (AttributeFilterData filterData : savedAttributeFilters) {
            attributeFilterList.addWidget(getFilterWidgetFromData(filterData));
        }
    }
    
    private void addAttributeFilters(JSONObject conditionArgs) {
        List<String> include = new ArrayList<String>(), exclude = new ArrayList<String>();
        for (AttributeFilterData filterData : savedAttributeFilters) {
            if (filterData.isInclude()) {
                include.add(filterData.getFilterString());
            } else {
                exclude.add(filterData.getFilterString());
            }
        }
        
        String includeSql = Utils.joinStrings(" OR ", include);
        String excludeSql = Utils.joinStrings(" OR ", exclude);
        addIfNonempty(conditionArgs, "include_attributes_where", includeSql);
        addIfNonempty(conditionArgs, "exclude_attributes_where", excludeSql);
    }

    public JSONObject getConditionArgs() {
        JSONObject conditionArgs = new JSONObject();
        addIfNonempty(conditionArgs, "extra_where", savedSqlCondition);
        addAttributeFilters(conditionArgs);
        
        if (!savedShowInvalid) {
            List<String> labelsToExclude = 
                Arrays.asList(new String[] {TestLabelManager.INVALIDATED_LABEL});
            conditionArgs.put("exclude_labels", Utils.stringsToJSON(labelsToExclude));
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
    
    private String getListKey(String base, int index) {
        return base + "_" + Integer.toString(index);
    }

    public void handleHistoryArguments(Map<String, String> arguments) {
        setSqlCondition(arguments.get("condition"));
        savedShowInvalid = Boolean.valueOf(arguments.get("show_invalid"));
        showInvalid.setChecked(savedShowInvalid);
        
        attributeFilterList.clear();
        for (int index = 0; ; index++) {
            AttributeFilterData filterData = AttributeFilterData.fromHistory(
                    arguments, getListKey("attribute", index));
            if (filterData == null) {
                break;
            }
            attributeFilterList.addWidget(getFilterWidgetFromData(filterData));
        }
    }
    
    public void addHistoryArguments(Map<String, String> arguments) {
        arguments.put("condition", savedSqlCondition);
        arguments.put("show_invalid", Boolean.toString(savedShowInvalid));
        int index = 0;
        for (AttributeFilterData filterData : savedAttributeFilters) {
            filterData.addToHistory(arguments, getListKey("attribute", index));
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
