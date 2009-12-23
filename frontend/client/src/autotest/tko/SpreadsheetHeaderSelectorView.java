package autotest.tko;

import autotest.common.ui.DoubleListSelector;
import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.MultiListSelectPresenter;
import autotest.common.ui.SimplifiedList;
import autotest.common.ui.ToggleControl;
import autotest.common.ui.ToggleLink;
import autotest.common.ui.MultiListSelectPresenter.DoubleListDisplay;
import autotest.common.ui.MultiListSelectPresenter.ToggleDisplay;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.StackPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.VerticalPanel;

public class SpreadsheetHeaderSelectorView extends Composite 
                                           implements MultiListSelectPresenter.ToggleDisplay,
                                                      SpreadsheetHeaderSelect.Display {
    protected final static String SWITCH_TO_SINGLE = "Switch to single";
    protected final static String SWITCH_TO_MULTIPLE = "Switch to multiple";
    static final String CANCEL_FIXED_VALUES = "Don't use fixed values";
    static final String USE_FIXED_VALUES = "Fixed values...";
    
    private ToggleLink fixedValuesToggle = new ToggleLink(USE_FIXED_VALUES, CANCEL_FIXED_VALUES);
    private TextArea fixedValues = new TextArea();
    private ExtendedListBox listBox = new ExtendedListBox();
    private DoubleListSelector doubleListDisplay = new DoubleListSelector();
    private StackPanel stack = new StackPanel();
    private ToggleLink multipleSelectToggle = new ToggleLink(SWITCH_TO_MULTIPLE, SWITCH_TO_SINGLE);
    
    public SpreadsheetHeaderSelectorView() {
        Panel singleHeaderOptions = new VerticalPanel();
        singleHeaderOptions.add(listBox);
        
        stack.add(singleHeaderOptions);
        stack.add(doubleListDisplay);

        Panel fixedValuePanel = new VerticalPanel();
        fixedValuePanel.add(fixedValuesToggle);
        fixedValuePanel.add(fixedValues);

        Panel panel = new VerticalPanel();
        panel.add(stack);
        panel.add(fixedValuePanel);
        panel.add(multipleSelectToggle);
        initWidget(panel);

        fixedValues.setVisible(false);
        fixedValues.addStyleName("fixed-headers-input");
    }

    @Override
    public HasText getFixedValuesInput() {
        return fixedValues;
    }

    @Override
    public ToggleLink getFixedValuesToggle() {
        return fixedValuesToggle;
    }

    @Override
    public void setFixedValuesVisible(boolean visible) {
        fixedValues.setVisible(visible);
    }

    @Override
    public DoubleListDisplay getDoubleListDisplay() {
        return doubleListDisplay;
    }

    @Override
    public ToggleDisplay getToggleDisplay() {
        return this;
    }

    @Override
    public SimplifiedList getSingleSelector() {
        return listBox;
    }

    @Override
    public ToggleControl getToggleMultipleLink() {
        return multipleSelectToggle;
    }

    @Override
    public void setDoubleListVisible(boolean doubleListVisible) {
        stack.showStack(doubleListVisible ? 1 : 0);
    }
}
