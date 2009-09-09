package autotest.tko;

import autotest.common.ui.DoubleListSelector;
import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.MultiListSelectPresenter;
import autotest.common.ui.SimplifiedList;
import autotest.common.ui.ToggleControl;
import autotest.common.ui.ToggleLink;
import autotest.common.ui.MultiListSelectPresenter.DoubleListDisplay;
import autotest.common.ui.MultiListSelectPresenter.ToggleDisplay;
import autotest.tko.HeaderSelect.MachineLabelDisplay;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.StackPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;

public class HeaderSelectorView extends Composite 
                                implements HeaderSelect.Display, 
                                           MultiListSelectPresenter.ToggleDisplay {
    private static class MachineLabelInput extends Composite 
                                           implements HeaderSelect.MachineLabelDisplay {
        private TextBox labelInput = new TextBox();
        
        public MachineLabelInput(String name) {
            Panel container = new HorizontalPanel();
            container.add(new Label(name + ": "));
            container.add(labelInput);
            initWidget(container);
        }
        
        @Override
        public HasText getLabelInput() {
            return labelInput;
        }
    }

    final static String SWITCH_TO_SINGLE = "Switch to single";
    final static String SWITCH_TO_MULTIPLE = "Switch to multiple";
    static final String CANCEL_FIXED_VALUES = "Don't use fixed values";
    static final String USE_FIXED_VALUES = "Fixed values...";

    private ExtendedListBox listBox = new ExtendedListBox();
    private ToggleLink fixedValuesToggle = new ToggleLink(USE_FIXED_VALUES, CANCEL_FIXED_VALUES);
    private TextArea fixedValues = new TextArea();
    private DoubleListSelector doubleListDisplay = new DoubleListSelector();
    private StackPanel stack = new StackPanel();
    private ToggleLink multipleSelectToggle = new ToggleLink(SWITCH_TO_MULTIPLE, SWITCH_TO_SINGLE);
    private Panel machineLabelInputPanel = new VerticalPanel();
    
    public HeaderSelectorView() {
        Panel singleHeaderOptions = new VerticalPanel();
        singleHeaderOptions.add(listBox);
        singleHeaderOptions.add(fixedValuesToggle);
        singleHeaderOptions.add(fixedValues);
        stack.add(singleHeaderOptions);
        stack.add(doubleListDisplay);

        Panel panel = new VerticalPanel();
        panel.add(stack);
        panel.add(multipleSelectToggle);
        panel.add(machineLabelInputPanel);
        initWidget(panel);

        fixedValues.setVisible(false);
        fixedValues.setSize("30em", "10em");
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
    public HasText getFixedValuesInput() {
        return fixedValues;
    }

    @Override
    public ToggleLink getFixedValuesToggle() {
        return fixedValuesToggle;
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

    @Override
    public void setFixedValuesVisible(boolean visible) {
        fixedValues.setVisible(visible);
    }

    @Override
    public MachineLabelDisplay addMachineLabelDisplay(String name) {
        MachineLabelInput input = new MachineLabelInput(name);
        machineLabelInputPanel.add(input);
        return input;
    }

    @Override
    public void removeMachineLabelDisplay(MachineLabelDisplay display) {
        machineLabelInputPanel.remove((MachineLabelInput) display);
    }
}
