package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.SimpleHyperlink;
import autotest.tko.TkoUtils.FieldInfo;
import autotest.tko.WidgetList.ListWidgetFactory;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HTMLPanel;
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

class CommonPanel extends Composite implements ClickHandler, PositionCallback {
    private static final String WIKI_URL = "http://autotest.kernel.org/wiki/TkoHowTo";
    private static final String SHOW_QUICK_REFERENCE = "Show quick reference";
    private static final String HIDE_QUICK_REFERENCE = "Hide quick reference";
    private static final String SHOW_CONTROLS = "Show controls";
    private static final String HIDE_CONTROLS = "Hide controls";
    private static final String INCLUDE_ATTRIBUTES_TABLE = "test_attributes_include";
    private static final String EXCLUDE_ATTRIBUTES_TABLE = "test_attributes_exclude";

    private static CommonPanel theInstance = new CommonPanel();

    private static abstract class FilterData {
        protected boolean isInclude;

        public boolean isInclude() {
            return isInclude;
        }

        public abstract String getFilterString();
        public abstract String getFilterType();
        public abstract void addToHistory(Map<String, String> args, String prefix);

        public static FilterData dataFromHistory(Map<String, String> args, String prefix) {
            String includeKey = prefix + "_include";
            if (!args.containsKey(includeKey)) {
                return null;
            }

            if (args.containsKey(prefix + "_attribute")) {
                return AttributeFilterData.fromHistory(args, prefix);
            } else {
                return LabelFilterData.fromHistory(args, prefix);
            }
        }
    }

    private static class AttributeFilterData extends FilterData {
        private String attributeWhere, valueWhere;

        public AttributeFilterData(boolean isInclude, String attributeWhere, String valueWhere) {
            this.isInclude = isInclude;
            this.attributeWhere = attributeWhere;
            this.valueWhere = valueWhere;
        }

        @Override
        public String getFilterString() {
            String tableName = isInclude ? INCLUDE_ATTRIBUTES_TABLE : EXCLUDE_ATTRIBUTES_TABLE;
            return "(" + tableName + ".attribute " + attributeWhere + " AND " +
                   tableName + ".value " + valueWhere + ")";
        }

        @Override
        public String getFilterType() {
            return FilterFactory.ATTRIBUTE_TYPE;
        }

        @Override
        public void addToHistory(Map<String, String> args, String prefix) {
            args.put(prefix + "_include", Boolean.toString(isInclude()));
            args.put(prefix + "_attribute", attributeWhere);
            args.put(prefix + "_value", valueWhere);
        }

        public static AttributeFilterData fromHistory(Map<String, String> args, String prefix) {
            String includeKey = prefix + "_include";
            boolean include = Boolean.valueOf(args.get(includeKey));
            String attributeWhere = args.get(prefix + "_attribute");
            String valueWhere = args.get(prefix + "_value");
            return new AttributeFilterData(include, attributeWhere, valueWhere);
        }
    }

    private static class LabelFilterData extends FilterData {
        private String labelWhere;

        public LabelFilterData(boolean isInclude, String labelWhere) {
            this.isInclude = isInclude;
            this.labelWhere = labelWhere;
        }

        @Override
        public String getFilterString() {
            return labelWhere;
        }

        @Override
        public String getFilterType() {
            return FilterFactory.LABEL_TYPE;
        }

        @Override
        public void addToHistory(Map<String, String> args, String prefix) {
            args.put(prefix + "_include", Boolean.toString(isInclude()));
            args.put(prefix + "_label", labelWhere);
        }

        public static LabelFilterData fromHistory(Map<String, String> args, String prefix) {
            String includeKey = prefix + "_include";
            boolean include = Boolean.valueOf(args.get(includeKey));
            String labelWhere = args.get(prefix + "_label");
            return new LabelFilterData(include, labelWhere);
      }
    }

    private abstract class TestFilterWidget extends Composite implements ClickHandler {
        protected ListBox includeOrExclude = new ListBox();

        protected boolean isInclude() {
            return includeOrExclude.getSelectedIndex() == 0;
        }

        protected void setupPanel(List<TextBox> textBoxes) {
            Panel panel = new HorizontalPanel();

            includeOrExclude.addItem("Include");
            includeOrExclude.addItem("Exclude");
            panel.add(includeOrExclude);

            for (TextBox textBox : textBoxes) {
                panel.add(new Label(textBox.getName()));
                panel.add(textBox);
            }

            SimpleHyperlink deleteLink = new SimpleHyperlink("[X]");
            deleteLink.addClickHandler(this);
            panel.add(deleteLink);

            initWidget(panel);
        }

        public void onClick(ClickEvent event) {
            filterList.deleteWidget(this);
        }

        public abstract FilterData getFilterData();
    }

    private class AttributeFilter extends TestFilterWidget {
        private TextBox attributeWhere = new TextBox(), valueWhere = new TextBox();

        public AttributeFilter() {
            attributeWhere.setName("tests with attribute");
            valueWhere.setName("and value");
            List<TextBox> textBoxes = Arrays.asList(attributeWhere, valueWhere);

            setupPanel(textBoxes);
        }

        @Override
        public FilterData getFilterData() {
            return new AttributeFilterData(isInclude(), attributeWhere.getText(),
                                           valueWhere.getText());
        }
    }

    private class LabelFilter extends TestFilterWidget {
        private TextBox labelWhere = new TextBox();

        public LabelFilter() {
            labelWhere.setName("tests with label");
            List<TextBox> textBoxes = Arrays.asList(labelWhere);

            setupPanel(textBoxes);
        }

        @Override
        public FilterData getFilterData() {
            return new LabelFilterData(isInclude(), labelWhere.getText());
        }
    }

    private class FilterFactory implements ListWidgetFactory<TestFilterWidget> {
        private static final String LABEL_TYPE = "Add label filter";
        private static final String ATTRIBUTE_TYPE = "Add attribute filter";

        public List<String> getWidgetTypes() {
            List<String> types = Arrays.asList(LABEL_TYPE, ATTRIBUTE_TYPE);

            return types;
        }

        public TestFilterWidget getNewWidget(String type) {
            if (type.equals(LABEL_TYPE)) {
                return new LabelFilter();
            } else {
                assert(type.equals(ATTRIBUTE_TYPE));
                return new AttributeFilter();
            }
        }

        public TestFilterWidget getFilterWidgetFromData(FilterData filterData) {
            TestFilterWidget filter = null;
            if (filterData.getFilterType().equals(FilterFactory.ATTRIBUTE_TYPE)) {
                AttributeFilter aFilter = new AttributeFilter();
                aFilter.attributeWhere.setText(((AttributeFilterData)filterData).attributeWhere);
                aFilter.valueWhere.setText(((AttributeFilterData)filterData).valueWhere);
                filter = aFilter;
            } else {
                assert(filterData.getFilterType().equals(FilterFactory.LABEL_TYPE));
                LabelFilter lFilter = new LabelFilter();
                lFilter.labelWhere.setText(((LabelFilterData)filterData).labelWhere);
                filter = lFilter;
            }
            filter.includeOrExclude.setSelectedIndex(filterData.isInclude() ? 0 : 1);

            return filter;
        }
    }

    private HTMLPanel htmlPanel;
    private TextArea customSqlBox = new TextArea();
    private CheckBox showInvalid = new CheckBox("Show invalidated tests");
    private SimpleHyperlink quickReferenceLink = new SimpleHyperlink(SHOW_QUICK_REFERENCE);
    private PopupPanel quickReferencePopup;
    private SimpleHyperlink showHideControlsLink = new SimpleHyperlink(HIDE_CONTROLS);
    private Panel allControlsPanel = RootPanel.get("common_all_controls");
    private Set<CommonPanelListener> listeners = new HashSet<CommonPanelListener>();
    private WidgetList<TestFilterWidget> filterList;
    private FilterFactory filterFactory = new FilterFactory();

    private String savedSqlCondition;
    private boolean savedShowInvalid = false;
    private List<FilterData> savedFilters = new ArrayList<FilterData>();

    public static interface CommonPanelListener {
        public void onSetControlsVisible(boolean visible);
    }

    private CommonPanel() {
        htmlPanel = Utils.divToPanel("common_panel");
        initWidget(htmlPanel);
    }

    public void initialize() {
        customSqlBox.setSize("50em", "5em");
        quickReferenceLink.addClickHandler(this);
        showHideControlsLink.addClickHandler(this);

        filterList = new WidgetList<TestFilterWidget>(filterFactory);
        Panel titlePanel = new HorizontalPanel();
        titlePanel.add(getFieldLabel("Test attributes:"));
        titlePanel.add(new HTML("&nbsp;<a href=\"" + WIKI_URL + "#attribute_filtering\" " +
                                "target=\"_blank\">[?]</a>"));
        Panel attributeFilters = new VerticalPanel();
        attributeFilters.setStyleName("box");
        attributeFilters.add(titlePanel);
        attributeFilters.add(filterList);

        Panel commonFilterPanel = new VerticalPanel();
        commonFilterPanel.add(customSqlBox);
        commonFilterPanel.add(attributeFilters);
        commonFilterPanel.add(showInvalid);
        htmlPanel.add(commonFilterPanel, "common_filters");
        htmlPanel.add(quickReferenceLink, "common_quick_reference");
        htmlPanel.add(showHideControlsLink, "common_show_hide_controls");
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
        Utils.setElementVisible("common_condition_div", visible);
    }

    public void setSqlCondition(String text) {
        savedSqlCondition = text;
    }

    public void updateStateFromView() {
        savedSqlCondition = customSqlBox.getText().trim();
        savedShowInvalid = showInvalid.getValue();

        savedFilters.clear();
        for (TestFilterWidget filter : filterList.getWidgets()) {
            savedFilters.add(filter.getFilterData());
        }
    }

    public void updateViewFromState() {
        customSqlBox.setText(savedSqlCondition);
        showInvalid.setValue(savedShowInvalid);

        filterList.clear();
        for (FilterData filterData : savedFilters) {
            filterList.addWidget(filterFactory.getFilterWidgetFromData(filterData));
        }
    }

    private void addAttributeFilters(JSONObject conditionArgs) {
        List<String> include = new ArrayList<String>(), exclude = new ArrayList<String>();

        getIncludeAndExclude(include, exclude, FilterFactory.ATTRIBUTE_TYPE);

        String includeSql = Utils.joinStrings(" OR ", include);
        String excludeSql = Utils.joinStrings(" OR ", exclude);
        addIfNonempty(conditionArgs, "include_attributes_where", includeSql);
        addIfNonempty(conditionArgs, "exclude_attributes_where", excludeSql);
    }

    private void addLabelFilters(JSONObject conditionArgs) {
        List<String> include = new ArrayList<String>(), exclude = new ArrayList<String>();

        getIncludeAndExclude(include, exclude, FilterFactory.LABEL_TYPE);

        if (!savedShowInvalid) {
            exclude.add(TestLabelManager.INVALIDATED_LABEL);
        }

        if (!include.isEmpty()) {
            conditionArgs.put("include_labels", Utils.stringsToJSON(include));
        }
        if (!exclude.isEmpty()) {
            conditionArgs.put("exclude_labels", Utils.stringsToJSON(exclude));
        }
    }

    private void getIncludeAndExclude(List<String> include, List<String> exclude, String type) {
        for (FilterData filterData : savedFilters) {
            if (filterData.getFilterType().equals(type)) {
                if (filterData.isInclude()) {
                    include.add(filterData.getFilterString());
                }
                else {
                    exclude.add(filterData.getFilterString());
                }
            }
        }
    }

    public JSONObject getConditionArgs() {
        JSONObject conditionArgs = new JSONObject();
        addIfNonempty(conditionArgs, "extra_where", savedSqlCondition);
        addAttributeFilters(conditionArgs);
        addLabelFilters(conditionArgs);

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

        savedFilters.clear();
        for (int index = 0; ; index++) {
            FilterData filterData = FilterData.dataFromHistory(
                    arguments, getListKey("filter", index));
            if (filterData == null) {
                break;
            }
            savedFilters.add(filterData);
        }

        updateViewFromState();
    }

    public void addHistoryArguments(Map<String, String> arguments) {
        arguments.put("condition", savedSqlCondition);
        arguments.put("show_invalid", Boolean.toString(savedShowInvalid));
        int index = 0;
        for (FilterData filterData : savedFilters) {
            filterData.addToHistory(arguments, getListKey("filter", index));
            index++;
        }
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
}
